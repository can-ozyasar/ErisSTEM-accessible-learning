"""Paired, locally blinded relevance review of retrieval results for PDF questions.

Both corpora are research-only and treat all candidates as available. Results are
not production metrics and pool judgments cannot measure unreturned evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
from collections import defaultdict
from pathlib import Path

from ..history_rag import load_index, matching_sections, retrieve
from ..question_bank_extract import extract_book
from ..question_bank_routes import _layout_contaminated


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def select_questions(book, index, per_section=2, seed=20261027):
    groups = defaultdict(list)
    for item in book['questions']:
        q = item['question']
        if item['issues'] or _layout_contaminated(q) or q.get('visuals'):
            continue
        topic = (book['page_contexts'].get(q['source']['page']) or {}).get('topic')
        sections = matching_sections(index, topic)
        if len(sections) != 1:
            continue
        public = {key: value for key, value in q.items() if key not in ('answer_label', 'answer_source_checked')}
        groups[sections[0]].append({'question': public, 'topic': topic, 'section_id': sections[0]})
    rng = random.Random(seed)
    selected = []
    for section in sorted(groups):
        available = sorted(groups[section], key=lambda x: x['question']['id'])
        selected.extend(rng.sample(available, min(per_section, len(available))))
    rng.shuffle(selected)
    return selected, {k: len(v) for k, v in sorted(groups.items())}


def prepare(book, index, experimental, per_section=2, seed=20261027, k=3):
    if experimental.get('schema') != 'history-rag-experimental-candidates-v1' or experimental.get('source_checksum') != index['source_checksum']:
        raise ValueError('experimental source mismatch')
    if per_section < 1 or k < 1:
        raise ValueError('invalid sample size')
    selected, populations = select_questions(book, index, per_section, seed)
    rng = random.Random(seed + 1)
    review_cases, mapping_cases = [], []
    for case in selected:
        q = case['question']
        query = ' '.join(part.get('text', '') for part in q['parts'])
        systems = {'baseline': index, 'experimental': {'sections': index['sections'], 'chunks': experimental['chunks']}}
        pool = {}
        ranks = {}
        for name, corpus in systems.items():
            hits = retrieve(corpus, {c['id'] for c in corpus['chunks']}, case['topic'], query, limit=k)
            ranks[name] = []
            for c in hits:
                evidence = {'page': c['page'], 'bbox': c['bbox'], 'text': c['text'],
                            'segments': c.get('segments', []), 'source_attributions': c.get('source_attributions', [])}
                identity = hashlib.sha256(canonical(evidence).encode()).hexdigest()[:20]
                pool[identity] = {'evidence_id': identity, **evidence, 'label': None,
                                  'reviewer': None, 'source_checked': False}
                ranks[name].append(identity)
        evidence = list(pool.values())
        rng.shuffle(evidence)
        review_cases.append({'question': q, 'section_id': case['section_id'], 'topic': case['topic'],
                             'question_source_checked': False, 'question_reviewer': None, 'evidence': evidence})
        mapping_cases.append({'question_id': q['id'], 'ranks': ranks})
    sample = {'schema': 'history-rag-paired-review-v1', 'question_source_checksum': book['source_checksum'],
              'evidence_source_checksum': index['source_checksum'], 'seed': seed, 'per_section': per_section,
              'eligible_section_counts': populations, 'k': k, 'cases': review_cases,
              'notice': 'Pooled candidates; neither system nor rank is shown. All sources are unapproved research candidates.'}
    mapping = {'schema': 'history-rag-paired-mapping-v1', 'sample_sha256': hashlib.sha256(canonical(sample).encode()).hexdigest(),
               'cases': mapping_cases}
    return sample, mapping


def score(sample, mapping, reviewed):
    if mapping.get('sample_sha256') != hashlib.sha256(canonical(sample).encode()).hexdigest():
        raise ValueError('sample or mapping mismatch')
    if any(reviewed.get(k) != sample[k] for k in ('schema', 'question_source_checksum', 'evidence_source_checksum', 'seed', 'per_section', 'eligible_section_counts', 'k')):
        raise ValueError('review metadata mismatch')
    expected = {c['question']['id']: c for c in sample['cases']}
    rows = reviewed.get('cases')
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError('case count mismatch')
    map_cases = mapping.get('cases')
    if not isinstance(map_cases, list) or len(map_cases) != len(expected):
        raise ValueError('mapping case count mismatch')
    mapping_ids = set()
    for mapped in map_cases:
        qid = mapped.get('question_id')
        if qid not in expected or qid in mapping_ids:
            raise ValueError('invalid mapping question id')
        mapping_ids.add(qid)
        available = {e['evidence_id'] for e in expected[qid]['evidence']}
        ranks = mapped.get('ranks', {})
        if set(ranks) != {'baseline', 'experimental'}:
            raise ValueError('invalid mapping systems')
        for ids in ranks.values():
            if not isinstance(ids, list) or len(ids) > sample['k'] or len(ids) != len(set(ids)) or not set(ids) <= available:
                raise ValueError('invalid mapping ranks')
    seen = set()
    labels = {}
    eligible_questions = set()
    for row in rows:
        qid = row['question']['id']
        if qid not in expected or qid in seen: raise ValueError('invalid question id')
        seen.add(qid)
        orig = expected[qid]
        if any(row.get(k) != orig[k] for k in ('question', 'section_id', 'topic')): raise ValueError('question changed')
        if row.get('question_source_checked') is True and isinstance(row.get('question_reviewer'), str) and row['question_reviewer'].strip():
            eligible_questions.add(qid)
        elif row.get('question_source_checked') is not False or row.get('question_reviewer') is not None:
            raise ValueError('invalid question check')
        originals = {e['evidence_id']: e for e in orig['evidence']}
        if len(row.get('evidence', [])) != len(originals): raise ValueError('pool size mismatch')
        observed = set()
        for item in row['evidence']:
            eid = item.get('evidence_id')
            if eid not in originals or eid in observed: raise ValueError('invalid evidence id')
            observed.add(eid)
            if any(item.get(k) != originals[eid][k] for k in ('page', 'bbox', 'text', 'segments', 'source_attributions')):
                raise ValueError('evidence changed')
            label = item.get('label')
            if label is None:
                if item.get('reviewer') is not None or item.get('source_checked') is not False: raise ValueError('invalid unreviewed evidence')
            elif label not in ('relevant', 'irrelevant', 'uncertain') or item.get('source_checked') is not True or not isinstance(item.get('reviewer'), str) or not item['reviewer'].strip():
                raise ValueError('invalid evidence review')
            labels[(qid, eid)] = label
    scores = {}
    for system in ('baseline', 'experimental'):
        completed = []
        for case in mapping['cases']:
            qid = case['question_id']
            ranked = [labels[(qid, eid)] for eid in case['ranks'][system]]
            if qid in eligible_questions and all(label is not None for label in ranked):
                completed.append(ranked)
        definite = [label for row in completed for label in row if label != 'uncertain']
        scores[system] = {'questions_evaluated': len(completed),
                          'questions_with_relevant': sum('relevant' in row for row in completed),
                          'relevant': definite.count('relevant'), 'irrelevant': definite.count('irrelevant'),
                          'uncertain': sum(row.count('uncertain') for row in completed),
                          'returned': sum(map(len, completed))}
    return {'schema': 'history-rag-paired-review-report-v1', 'sample_questions': len(expected), 'scores': scores,
            'notice': 'Pooled top-k relevance judgments, not recall of all relevant evidence; all candidates treated as available, labels may be AI and are not independent expert validation.'}


def write(path, obj):
    root=(Path(__file__).resolve().parents[4]/'data/private').resolve()
    if not path.resolve().is_relative_to(root): raise ValueError('output must be inside data/private')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(obj,f,ensure_ascii=False,indent=2)


def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='action',required=True)
    create=sub.add_parser('prepare')
    for arg in ('question-pdf','source','index','experimental','sample','mapping'): create.add_argument('--'+arg,type=Path,required=True)
    assess=sub.add_parser('score')
    for arg in ('sample','mapping','reviewed','output'): assess.add_argument('--'+arg,type=Path,required=True)
    a=p.parse_args()
    if a.action=='prepare':
        index=load_index(a.source,a.index)
        sample,mapping=prepare(extract_book(a.question_pdf),index,json.loads(a.experimental.read_text(encoding='utf-8')))
        write(a.sample,sample);write(a.mapping,mapping)
        print(json.dumps({'questions':len(sample['cases']),'eligible':sample['eligible_section_counts'],'pool':sum(len(c['evidence']) for c in sample['cases'])},ensure_ascii=False))
    else:
        result=score(*(json.loads(getattr(a,k).read_text(encoding='utf-8')) for k in ('sample','mapping','reviewed')))
        write(a.output,result);print(json.dumps(result['scores'],ensure_ascii=False))

if __name__=='__main__':main()
