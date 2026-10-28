"""Freeze conservative question groups and score expert-reviewed answerability.

Research tooling only: exposure tracking is limited to supplied local records;
no expert identity, answer truth, or corpus completeness is inferred.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from .history_rag_paired_review import canonical, write


def exposure(paths):
    ids, pages = set(), set()
    for path in paths:
        obj = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(obj, dict):
            continue
        for case in obj.get('cases', []):
            if not isinstance(case, dict):
                continue
            q = case.get('question')
            if isinstance(q, dict) and q.get('id'):
                ids.add(q['id'])
                page = q.get('source', {}).get('page')
                if isinstance(page, int): pages.add(page)
        for pair in obj.get('advisory_pairs_before_grouping', []):
            ids.update(pair.get('question_ids', []))
            pages.update(p for p in pair.get('pages', []) if isinstance(p, int))
        if obj.get('schema') == 'history-rag-sealed-input-v1':
            for q in obj.get('queries', []):
                ids.add(q['question_id']); pages.add(q['page'])
    return ids, pages


def freeze(clusters, section_ids, exposed_ids, exposed_pages, seed='20261030'):
    if clusters.get('schema') != 'history-rag-reviewed-clusters-v1':
        raise ValueError('invalid clusters')
    rows = clusters['questions']
    if len({r['question_id'] for r in rows}) != len(rows): raise ValueError('duplicate question')
    blocked = {r['group_id'] for r in rows if r['question_id'] in exposed_ids or r['page'] in exposed_pages
               or r.get('previously_exposed') or r.get('group_exposed')}
    grouped = defaultdict(list)
    for row in rows:
        if row['group_id'] not in blocked: grouped[row['group_id']].append(row)
    # Whole groups are assigned together; one test group per covered section,
    # with deterministic hash order. Group overlap across sections is rejected.
    by_section = defaultdict(list)
    for group, members in grouped.items():
        sections = {r['section_id'] for r in members}
        if len(sections) != 1: raise ValueError('cross-section group requires manual review')
        by_section[sections.pop()].append(group)
    assignment = {}
    for section, groups in by_section.items():
        ordered = sorted(groups, key=lambda g: hashlib.sha256(f'{seed}:{section}:{g}'.encode()).hexdigest())
        for i, group in enumerate(ordered):
            assignment[group] = 'test' if i == 0 and len(ordered) >= 2 else 'development'
    output = [{'question_id': r['question_id'], 'page': r['page'], 'section_id': r['section_id'],
               'group_id': r['group_id'], 'split': assignment[r['group_id']]}
              for r in rows if r['group_id'] in assignment]
    counts = {s: dict(Counter(r['split'] for r in output if r['section_id'] == s)) for s in section_ids}
    return {'schema':'history-rag-independent-candidates-v1',
            'question_source_checksum':clusters['question_source_checksum'],
            'evidence_source_checksum':clusters['evidence_source_checksum'], 'seed':seed,
            'exposure_page_count':len(exposed_pages), 'exposure_question_count':len(exposed_ids),
            'section_counts':counts, 'questions':output,
            'notice':'Candidates only; incomplete historical exposure and semantic duplicates remain. No expert labels or production approval.'}


def prepare_development(manifest, book, index, experimental):
    from ..history_rag import retrieve
    if manifest.get('schema') != 'history-rag-independent-candidates-v1' or manifest['question_source_checksum'] != book['source_checksum'] or manifest['evidence_source_checksum'] != index['source_checksum'] or experimental.get('source_checksum') != index['source_checksum']:
        raise ValueError('source checksum mismatch')
    questions = {x['question']['id']: x['question'] for x in book['questions']}
    sections = {s['id']: s['title'] for s in index['sections']}
    chunks = experimental['chunks']
    corpus = {'sections':index['sections'], 'chunks':chunks}
    cases = []
    for row in manifest['questions']:
        if row['split'] != 'development': continue
        q = questions[row['question_id']]
        query = ' '.join(part.get('text','') for part in q['parts'])
        hits = retrieve(corpus, {c['id'] for c in chunks}, sections[row['section_id']], query, limit=3)
        clean_q = {k:v for k,v in q.items() if k not in ('answer_label','answer_source_checked')}
        evidence = [{k:c.get(k, [] if k in ('segments','source_attributions') else None) for k in ('id','page','bbox','text','segments','source_attributions')} for c in hits]
        for kind, sources in [('retrieved',evidence),('empty_control',[])]:
            cases.append({'case_id':q['id']+':'+kind, 'kind':kind, 'section_id':row['section_id'],
                          'question':clean_q, 'choice_labels':[c['label'] for c in q['choices']], 'evidence':sources})
    if not cases: raise ValueError('no development cases')
    return {'schema':'history-rag-answerability-bundle-v1', 'split':'development',
            'question_source_checksum':book['source_checksum'], 'evidence_source_checksum':index['source_checksum'],
            'manifest_sha256':digest(manifest), 'cases':cases,
            'notice':'Private research candidates, not approved. Empty controls are constructed; they do not estimate natural unanswerable prevalence.'}


def digest(obj): return hashlib.sha256(canonical(obj).encode()).hexdigest()


def score(bundle, labels, predictions):
    if bundle.get('schema') != 'history-rag-answerability-bundle-v1': raise ValueError('invalid bundle')
    fingerprint = digest(bundle)
    if labels.get('bundle_sha256') != fingerprint or predictions.get('bundle_sha256') != fingerprint:
        raise ValueError('bundle checksum mismatch')
    cases = bundle.get('cases', [])
    if not cases or len({x['case_id'] for x in cases}) != len(cases): raise ValueError('invalid cases')
    gold = labels.get('cases', []); pred = predictions.get('cases', [])
    for name, rows in [('labels', gold), ('predictions', pred)]:
        if len(rows) != len(cases) or {x.get('case_id') for x in rows} != {x['case_id'] for x in cases}:
            raise ValueError(f'{name} incomplete or duplicate')
    gold = {x['case_id']:x for x in gold}; pred = {x['case_id']:x for x in pred}
    out = Counter(); correctness = Counter()
    for case in cases:
        cid=case['case_id']; g=gold[cid]; p=pred[cid]
        if g.get('source_checked') is not True or not isinstance(g.get('reviewer'),str) or not g['reviewer'].strip():
            raise ValueError('every case needs source-checked review')
        answerability=g.get('answerability'); action=p.get('action')
        if answerability not in ('sufficient','insufficient','uncertain') or action not in ('answer','abstain'):
            raise ValueError('invalid label or action')
        if answerability == 'sufficient':
            if g.get('answer_label') not in case['choice_labels']: raise ValueError('missing validated answer')
        elif g.get('answer_label') is not None: raise ValueError('unsupported case must not have gold answer')
        answer=p.get('answer_label')
        if action == 'answer' and answer not in case['choice_labels']: raise ValueError('invalid predicted answer')
        if action == 'abstain' and answer is not None: raise ValueError('abstention includes answer')
        out[f'{answerability}_{action}']+=1
        if answerability == 'sufficient' and action == 'answer':
            correctness['correct' if answer == g['answer_label'] else 'incorrect']+=1
    return {'schema':'history-rag-answerability-report-v1','bundle_sha256':fingerprint,
            'cases':len(cases), 'counts':dict(out), 'answer_correctness_given_sufficient_and_answered':dict(correctness),
            'notice':'Uncertain cases are reported separately. Correctness does not establish grounded reasoning; expert labels and fixed evidence are prerequisites.'}


def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='action',required=True)
    f=sub.add_parser('freeze'); f.add_argument('--clusters',type=Path,required=True);f.add_argument('--index',type=Path,required=True)
    f.add_argument('--exposure-dir',type=Path,action='append',required=True);f.add_argument('--exposure-file',type=Path,action='append',default=[]);f.add_argument('--output',type=Path,required=True)
    d=sub.add_parser('prepare-development')
    for a in ('manifest','question-pdf','source','index','experimental','output'):d.add_argument('--'+a,type=Path,required=True)
    s=sub.add_parser('score')
    for a in ('bundle','labels','predictions','output'):s.add_argument('--'+a,type=Path,required=True)
    a=parser.parse_args()
    if a.action=='freeze':
        files=sorted({p for d in a.exposure_dir for p in d.glob('*.json')} | set(a.exposure_file))
        ids,pages=exposure(files);clusters=json.loads(a.clusters.read_text());index=json.loads(a.index.read_text())
        if clusters['evidence_source_checksum'] != index['source_checksum']: raise ValueError('index checksum mismatch')
        result=freeze(clusters,[s['id'] for s in index['sections']],ids,pages)
    elif a.action=='prepare-development':
        from ..history_rag import load_index
        from ..question_bank_extract import extract_book
        result=prepare_development(json.loads(a.manifest.read_text()), extract_book(a.question_pdf), load_index(a.source,a.index), json.loads(a.experimental.read_text()))
    else:
        result=score(*(json.loads(getattr(a,k).read_text()) for k in ('bundle','labels','predictions')))
    write(a.output,result); print(json.dumps({k:v for k,v in result.items() if k not in ('questions','notice','cases')},ensure_ascii=False))

if __name__=='__main__': main()
