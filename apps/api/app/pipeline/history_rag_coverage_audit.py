"""Sample PDF text blocks absent from the current index, for local coverage review.

This inventories blocks >= 40 characters only within indexed TOC page ranges; it
cannot measure page-level recall, OCR omissions, or all information in a PDF.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
from collections import defaultdict
from pathlib import Path

import pymupdf
from ..history_rag import _clean, load_index


def inventory(pdf, index):
    indexed = {item['id'] for item in index['chunks']}
    groups = defaultdict(list)
    seen = set()
    for section in index['sections']:
        for page_number in range(section['start'], min(section['end'], pdf.page_count) + 1):
            page = pdf[page_number - 1]
            for block in page.get_text('dict')['blocks']:
                if block['type'] != 0:
                    continue
                text = _clean(' '.join(''.join(span['text'] for span in line['spans'])
                                       for line in block['lines']))
                if len(text) < 40:
                    continue
                box = [round(float(n), 2) for n in block['bbox']]
                key = f"{index['source_checksum']}:{page_number}:{box}:{text}"
                identity = hashlib.sha256(key.encode()).hexdigest()[:20]
                if identity in indexed or identity in seen:
                    continue
                seen.add(identity)
                groups[section['id']].append({'chunk_id': identity, 'section_id': section['id'],
                    'page': page_number, 'bbox': box, 'text': text,
                    'label': None, 'reviewer': None, 'source_checked': False})
    return groups


def sample_omissions(pdf, index, seed=20261026, per_section=3):
    if not 1 <= per_section <= 100:
        raise ValueError('per_section out of range')
    groups = inventory(pdf, index)
    rng = random.Random(seed)
    items = []
    for section in sorted(groups):
        items.extend(rng.sample(sorted(groups[section], key=lambda x: x['chunk_id']),
                                min(per_section, len(groups[section]))))
    rng.shuffle(items)
    return {'schema': 'history-rag-omitted-block-audit-v1', 'source_checksum': index['source_checksum'],
            'seed': seed, 'per_section': per_section,
            'section_population': {k: len(v) for k, v in sorted(groups.items())},
            'items': items,
            'notice': 'PDF extracted text blocks of at least 40 characters absent from the index, within indexed page ranges only. No approvals.'}


def evaluate_omissions(pdf, index, sample):
    if sample.get('seed') != 20261026 or sample.get('per_section') != 3:
        raise ValueError('unexpected sampling protocol')
    expected = sample_omissions(pdf, index)
    for k in ('schema', 'source_checksum', 'section_population'):
        if sample.get(k) != expected[k]:
            raise ValueError('sample metadata mismatch')
    original = {x['chunk_id']: x for x in expected['items']}
    if len(sample.get('items', [])) != len(original):
        raise ValueError('sample size mismatch')
    seen = set()
    counts = defaultdict(int)
    for item in sample['items']:
        identity = item.get('chunk_id')
        if identity not in original or identity in seen:
            raise ValueError('missing, foreign or duplicate item')
        seen.add(identity)
        if any(item.get(k) != original[identity][k] for k in ('section_id', 'page', 'bbox', 'text')):
            raise ValueError('sample content changed')
        label = item.get('label')
        if label is None:
            if item.get('source_checked') is not False or item.get('reviewer') is not None:
                raise ValueError('invalid unreviewed item')
            continue
        if label not in ('useful', 'not_useful', 'uncertain') or item.get('source_checked') is not True or not isinstance(item.get('reviewer'), str) or not item['reviewer'].strip():
            raise ValueError('invalid review')
        counts[label] += 1
    return {'schema': 'history-rag-omitted-block-report-v1', 'source_checksum': index['source_checksum'],
            'sample_size': len(original), 'labeled': sum(counts.values()), 'labels': dict(counts),
            'section_population': expected['section_population'],
            'notice': 'Descriptive stratified omitted-block sample, not overall retrieval recall; AI labels are not expert validation.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--reviewed', type=Path)
    args = p.parse_args()
    root = (Path(__file__).resolve().parents[4] / 'data/private').resolve()
    if not args.output.resolve().is_relative_to(root):
        raise ValueError('output must be inside data/private')
    index = load_index(args.source, args.index)
    with pymupdf.open(args.source) as pdf:
        result = evaluate_omissions(pdf, index, json.loads(args.reviewed.read_text(encoding='utf-8'))) if args.reviewed else sample_omissions(pdf, index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({'sample_size': len(result['items']) if 'items' in result else result['sample_size'],
                      'section_population': result['section_population']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
