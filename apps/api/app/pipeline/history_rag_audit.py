"""Blind, section-stratified local audit of indexed history chunks.

This audits existing candidates only; blocks excluded before indexing are out of scope.
No data is approved, uploaded, removed or added to retrieval.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path
from ..history_rag import candidate_review_warnings, load_index

LABELS = {'lesson_fact', 'activity', 'caption', 'incomplete', 'extraction_error', 'other'}
BAD = LABELS - {'lesson_fact'}


def create_sample(index: dict, per_section: int, seed: int) -> dict:
    if per_section < 1 or per_section > 100:
        raise ValueError('per_section must be between 1 and 100')
    grouped = defaultdict(list)
    ids = set()
    for chunk in index['chunks']:
        if chunk['id'] in ids: raise ValueError('duplicate chunk id')
        ids.add(chunk['id']); grouped[chunk['section_id']].append(chunk)
    rng = random.Random(seed)
    sample = []
    sizes = {}
    for section in sorted(grouped):
        chunks = sorted(grouped[section], key=lambda c: c['id'])
        sizes[section] = len(chunks)
        for c in rng.sample(chunks, min(per_section, len(chunks))):
            sample.append({'chunk_id': c['id'], 'section_id': section, 'page': c['page'],
                           'bbox': c['bbox'], 'text': c['text'], 'label': None,
                           'reviewer': None, 'source_checked': False})
    rng.shuffle(sample)
    return {'schema': 'history-rag-blind-audit-v1', 'source_checksum': index['source_checksum'],
            'seed': seed, 'per_section': per_section, 'section_population': sizes, 'items': sample,
            'notice': 'Blind sample of indexed candidates; never an approval or a training dataset.'}


def evaluate(index: dict, sample: dict) -> dict:
    if sample.get('schema') != 'history-rag-blind-audit-v1' or sample.get('source_checksum') != index['source_checksum']:
        raise ValueError('schema or source checksum mismatch')
    expected = create_sample(index, sample['per_section'], sample['seed'])
    if sample.get('section_population') != expected['section_population']:
        raise ValueError('population mismatch')
    original = {item['chunk_id']: item for item in expected['items']}
    items = sample.get('items')
    if not isinstance(items, list) or len(items) != len(original): raise ValueError('sample size mismatch')
    seen, complete, categories = set(), [], Counter()
    for item in items:
        identity = item.get('chunk_id')
        if identity not in original or identity in seen: raise ValueError('missing, duplicate or foreign item')
        seen.add(identity); o = original[identity]
        if any(item.get(k) != o[k] for k in ('section_id', 'page', 'bbox', 'text')):
            raise ValueError('sample content changed')
        label = item.get('label')
        if label is None:
            if item.get('source_checked') is not False or item.get('reviewer') is not None:
                raise ValueError('unlabeled item must remain unreviewed')
            continue
        if label not in LABELS or item.get('source_checked') is not True or not isinstance(item.get('reviewer'), str) or not item['reviewer'].strip():
            raise ValueError('label requires reviewer and source check')
        categories[label] += 1
        complete.append((item, bool(candidate_review_warnings(item['text']))))
    flagged = sum(flag for _, flag in complete)
    bad = sum(item['label'] in BAD for item, _ in complete)
    tp = sum(flag and item['label'] in BAD for item, flag in complete)
    fully_labeled = len(complete) == len(items)
    return {'schema': 'history-rag-audit-report-v1', 'source_checksum': index['source_checksum'],
            'sample_size': len(items), 'labeled': len(complete), 'complete': fully_labeled,
            'labels': dict(categories), 'flagged': flagged, 'bad': bad, 'flagged_bad': tp,
            'precision_on_labeled': tp/flagged if flagged else None,
            'recall_on_labeled': tp/bad if bad else None,
            'warning': 'Descriptive sample metrics only. Partial or unequal section sampling is not population-representative; exclusion from the original index is unmeasured.'}


def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='action',required=True)
    for name in ('sample','evaluate'):
        cmd=sub.add_parser(name); cmd.add_argument('--source',type=Path,required=True); cmd.add_argument('--index',type=Path,required=True)
        cmd.add_argument('--output',type=Path,required=True)
        if name == 'sample': cmd.add_argument('--per-section',type=int,default=5); cmd.add_argument('--seed',type=int,default=2026)
        else: cmd.add_argument('--sample',type=Path,required=True)
    args=p.parse_args(); root=(Path(__file__).resolve().parents[4]/'data/private').resolve(); target=args.output.resolve()
    if not target.is_relative_to(root): raise ValueError('output must be in data/private')
    index=load_index(args.source,args.index)
    result=create_sample(index,args.per_section,args.seed) if args.action == 'sample' else evaluate(index,json.loads(args.sample.read_text(encoding='utf-8')))
    target.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'action':args.action,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                      'items':len(result['items']) if args.action=='sample' else result['labeled']},ensure_ascii=False))

if __name__=='__main__': main()
