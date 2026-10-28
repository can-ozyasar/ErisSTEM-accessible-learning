"""Blind pooled comparison of exact and plural-normalized lexical retrieval.

Research only: all candidates are considered available, never production approval.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path

from ..history_rag import load_index, retrieve
from ..question_bank_extract import extract_book
from .history_rag_morphology_probe import retrieve_plural_probe
from .history_rag_paired_review import canonical, select_questions, write
from .history_rag_routing_experiment import PENALIZED, score


def prepare(book, index, experimental, previous_samples, seed=20261029, k=3):
    if experimental.get('schema') != 'history-rag-experimental-candidates-v1' or experimental.get('source_checksum') != index['source_checksum']:
        raise ValueError('experimental source mismatch')
    if any(sample.get('question_source_checksum') != book['source_checksum'] for sample in previous_samples):
        raise ValueError('question source mismatch')
    excluded = {case['question']['id'] for sample in previous_samples for case in sample['cases']}
    filtered = {**book, 'questions': [item for item in book['questions'] if item['question']['id'] not in excluded]}
    selected, populations = select_questions(filtered, index, 2, seed)
    corpus = {'sections': index['sections'], 'chunks': experimental['chunks']}
    ids = {item['id'] for item in corpus['chunks']}
    rng = random.Random(seed + 1)
    review_cases, mappings = [], []
    for case in selected:
        question = case['question']
        query = ' '.join(part.get('text', '') for part in question['parts'])
        exact = retrieve(corpus, ids, case['topic'], query, limit=k)
        plural = retrieve_plural_probe(corpus, ids, case['topic'], query, k=len(ids))
        quality = sorted(plural, key=lambda c: (-c['score'] * (.25 if PENALIZED.intersection(c.get('review_flags', [])) else 1), c['page'], c['id']))[:k]
        # Internal names are retained to share the integrity-checked scoring implementation.
        systems = {'topic': exact, 'quality': plural[:k], 'routing_quality': quality}
        pool, ranks = {}, {}
        for name, hits in systems.items():
            ranks[name] = []
            for item in hits:
                evidence = {key: item.get(key, [] if key in ('segments', 'source_attributions') else None)
                            for key in ('page', 'bbox', 'text', 'segments', 'source_attributions')}
                eid = hashlib.sha256(canonical(evidence).encode()).hexdigest()[:20]
                pool[eid] = {'evidence_id': eid, **evidence, 'label': None, 'reviewer': None, 'source_checked': False}
                ranks[name].append(eid)
        evidence = list(pool.values())
        rng.shuffle(evidence)
        review_cases.append({'question': question, 'topic': case['topic'], 'section_id': case['section_id'],
                             'question_source_checked': False, 'question_reviewer': None, 'evidence': evidence})
        mappings.append({'question_id': question['id'], 'ranks': ranks, 'routing': {'switched': False}})
    sample = {'schema': 'history-rag-routing-review-v1', 'question_source_checksum': book['source_checksum'],
              'evidence_source_checksum': index['source_checksum'], 'seed': seed, 'k': k,
              'excluded_question_ids': sorted(excluded), 'eligible_section_counts': populations, 'cases': review_cases,
              'notice': 'Blind pooled lexical comparison; unapproved research candidates; near-duplicate questions not excluded.'}
    mapping = {'schema': 'history-rag-routing-mapping-v1', 'sample_sha256': hashlib.sha256(canonical(sample).encode()).hexdigest(),
               'cases': mappings, 'system_meanings': {'topic': 'exact', 'quality': 'plural', 'routing_quality': 'plural_plus_content_penalty'}}
    return sample, mapping


def main():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest='action', required=True)
    create = sub.add_parser('prepare')
    for name in ('question-pdf', 'source', 'index', 'experimental', 'previous-one', 'previous-two', 'sample', 'mapping'):
        create.add_argument('--' + name, type=Path, required=True)
    evaluate = sub.add_parser('score')
    for name in ('sample', 'mapping', 'reviewed', 'output'):
        evaluate.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    if args.action == 'prepare':
        index = load_index(args.source, args.index)
        sample, mapping = prepare(extract_book(args.question_pdf), index,
                                  json.loads(args.experimental.read_text(encoding='utf-8')),
                                  [json.loads(args.previous_one.read_text(encoding='utf-8')), json.loads(args.previous_two.read_text(encoding='utf-8'))])
        write(args.sample, sample); write(args.mapping, mapping)
        print(json.dumps({'questions': len(sample['cases']), 'pool': sum(len(x['evidence']) for x in sample['cases'])}))
    else:
        sample, mapping, reviewed = (json.loads(getattr(args, name).read_text(encoding='utf-8')) for name in ('sample', 'mapping', 'reviewed'))
        report = score(sample, mapping, reviewed)
        report['system_meanings'] = mapping['system_meanings']
        report['notice'] = 'Top-k provisional relevance judgments on unapproved candidates; not production performance, answer correctness, or corpus recall.'
        write(args.output, report)
        print(json.dumps(report['scores'], ensure_ascii=False))


if __name__ == '__main__':
    main()
