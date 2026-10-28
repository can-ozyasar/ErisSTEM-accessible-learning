"""Build local, unapproved experimental candidates with source regions intact."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path

import pymupdf
from ..history_rag import _clean, load_index
from .history_rag_coverage_audit import evaluate_omissions
from .history_rag_layout_audit import CITATION, LOWER_START, TERMINAL, analyze


def block_records(page):
    result = []
    for block in page.get_text('dict')['blocks']:
        if block.get('type') != 0:
            continue
        text = _clean(' '.join(''.join(s['text'] for s in line['spans']) for line in block['lines']))
        if text:
            result.append({'bbox': [round(float(v), 2) for v in block['bbox']], 'text': text})
    return result


def candidate(item, page, checksum):
    """Build a versioned candidate; all contextual regions remain separately attributed."""
    box = pymupdf.Rect(item['bbox'])
    original = item['text']
    diagnostic = analyze(item, page)
    body = diagnostic['proposed_soft_hyphen_text'] or original
    blocks = block_records(page)
    neighbors = []
    citations = []
    for block in blocks:
        b = pymupdf.Rect(block['bbox'])
        if b == box:
            continue
        overlap = max(0, min(box.x1, b.x1) - max(box.x0, b.x0))
        if overlap < .75 * min(box.width, b.width):
            continue
        gap_before = box.y0 - b.y1
        gap_after = b.y0 - box.y1
        if -5 <= gap_after <= 35 and CITATION.search(block['text']) and len(block['text']) <= 150:
            citations.append({'page': item['page'], **block})
            continue
        if 0 <= gap_before <= 12 and LOWER_START.match(original) and not TERMINAL.search(block['text']):
            neighbors.append(('before', gap_before, block))
        if 0 <= gap_after <= 12 and not TERMINAL.search(original) and LOWER_START.match(block['text']):
            neighbors.append(('after', gap_after, block))
    # Ambiguous neighbors are not joined; an activity or table could be adjacent.
    context = []
    for side in ('before', 'after'):
        found = [v for v in neighbors if v[0] == side]
        if len(found) == 1:
            _, _, block = found[0]
            context.append({'position': side, 'page': item['page'], **block})
    # A quoted source may span several distinct PDF blocks. Keep each region
    # separate and continue only through an unambiguous adjacent same-column block.
    if original.startswith(('“', '‘')) and not original.rstrip().endswith(('”', '’')):
        context = [c for c in context if c['position'] != 'after']
        current = box
        for _ in range(3):
            options = []
            for block in blocks:
                b = pymupdf.Rect(block['bbox'])
                overlap = max(0, min(current.x1, b.x1) - max(current.x0, b.x0))
                if 0 <= b.y0 - current.y1 <= 12 and overlap >= .75 * min(current.width, b.width) and not CITATION.search(block['text']):
                    options.append(block)
            if len(options) != 1:
                break
            next_block = options[0]
            context.append({'position': 'after', 'page': item['page'], **next_block})
            current = pymupdf.Rect(next_block['bbox'])
            if next_block['text'].rstrip().endswith(('”', '’')):
                for block in blocks:
                    b = pymupdf.Rect(block['bbox'])
                    overlap = max(0, min(current.x1, b.x1) - max(current.x0, b.x0))
                    if -5 <= b.y0 - current.y1 <= 35 and overlap >= .75 * min(current.width, b.width) and CITATION.search(block['text']) and len(block['text']) <= 150:
                        citations.append({'page': item['page'], **block})
                break
    segments = ([c for c in context if c['position'] == 'before'] +
                [{'position': 'body', 'page': item['page'], 'bbox': item['bbox'], 'text': body}] +
                [c for c in context if c['position'] == 'after'])
    identity_material = json.dumps({'checksum': checksum, 'original_id': item.get('chunk_id', item.get('id')),
                                    'segments': segments, 'citations': citations}, ensure_ascii=False, sort_keys=True)
    return {'id': hashlib.sha256(identity_material.encode()).hexdigest()[:20],
            'original_id': item.get('chunk_id', item.get('id')), 'section_id': item['section_id'],
            'page': item['page'], 'bbox': item['bbox'], 'text': ' '.join(s['text'] for s in segments),
            'segments': segments, 'source_attributions': citations,
            'review_flags': diagnostic['flags'], 'review_status': 'experimental_unapproved'}


def build(index, pdf, reviewed):
    evaluate_omissions(pdf, index, reviewed)
    selected = [x for x in reviewed['items'] if x['label'] == 'useful']
    originals = index['chunks']
    experimental = [candidate(item, pdf[item['page'] - 1], index['source_checksum']) for item in originals + selected]
    return {'schema': 'history-rag-experimental-candidates-v1', 'source_checksum': index['source_checksum'],
            'base_count': len(originals), 'added_review_sample_count': len(selected), 'chunks': experimental,
            'notice': 'Research prototype. Added items were selected from AI-reviewed sample; not independent, exhaustive, approved or deployable.'}


def main():
    p = argparse.ArgumentParser()
    for arg in ('source', 'index', 'omitted-reviewed', 'output'):
        p.add_argument('--' + arg, type=Path, required=True)
    args = p.parse_args()
    root = (Path(__file__).resolve().parents[4] / 'data/private').resolve()
    if not args.output.resolve().is_relative_to(root):
        raise ValueError('output must be inside data/private')
    index = load_index(args.source, args.index)
    reviewed = json.loads(args.omitted_reviewed.read_text(encoding='utf-8'))
    with pymupdf.open(args.source) as pdf:
        result = build(index, pdf, reviewed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({'candidates': len(result['chunks']), 'added': result['added_review_sample_count'],
                      'with_attribution': sum(bool(x['source_attributions']) for x in result['chunks']),
                      'with_context': sum(len(x['segments']) > 1 for x in result['chunks'])}))


if __name__ == '__main__':
    main()
