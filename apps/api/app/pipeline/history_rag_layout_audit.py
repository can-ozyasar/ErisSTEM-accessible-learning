"""Experimental, read-only layout diagnostics for existing RAG candidates.

Outputs are review aids, not a replacement index or an approval decision.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from ..history_rag import _clean, candidate_review_warnings, load_index
from .history_rag_audit import BAD, LABELS, evaluate

INSTRUCTION = re.compile(r'\b(?:adım|etkinlik|yönerge|dereceli puanlama|performans görevi|öz değerlendirme|değerlendirme formu|karekod|öğrencinin|öğretmeniniz|sınıf arkadaş|puanlama anahtarı)\w*', re.IGNORECASE)
CAPTION = re.compile(r'\b(?:görsel|fotoğraf|resim|harita|tablo)\s*\d|\bmüzesi\b|\bmuseum\b', re.IGNORECASE)
RUBRIC = re.compile(r'\b(?:zihin haritası|görseller metni|seçtiği orta çağ|puanlama anahtarı|değerlendirme sistemi|ölçüt(?:ler)?|sunulmuştur|araştırmada bazı görseller)\b', re.IGNORECASE)
CITATION = re.compile(r'\b(?:s\.\s*\d+|(?:19|20)\d{2}\s*,\s*s\.)', re.IGNORECASE)
REFERENCE = re.compile(r'\b(?:kaynakça|erişim tarihi|yayınevi|isbn)\b', re.IGNORECASE)
TERMINAL = re.compile(r'[.!?…][”’"\')\]]*$')
LOWER_START = re.compile(r'^[a-zçğıöşü]')


def analyze(item: dict, page) -> dict:
    """Compare a chunk with actual intersecting PDF lines, retaining source text."""
    box = pymupdf.Rect(item['bbox'])
    lines = []
    nearby = []
    for block in page.get_text('dict')['blocks']:
        if block.get('type') != 0:
            continue
        for line in block['lines']:
            rect = pymupdf.Rect(line['bbox'])
            intersection = rect & box
            value = ''.join(span['text'] for span in line['spans']).strip()
            if rect.y0 >= box.y1 and rect.y0 - box.y1 <= 35 and rect.x1 >= box.x0 and rect.x0 <= box.x1:
                nearby.append(value)
            if rect.get_area() and intersection.get_area() / rect.get_area() >= .8 and value:
                lines.append(value)
    text = item['text'].strip()
    flags = []
    soft_breaks = [line for line in lines[:-1] if line.endswith('\xad')]
    if soft_breaks or any(re.search(r'[\wçğıöşüÇĞİÖŞÜ]-\s*$', line) for line in lines[:-1]):
        flags.append('satir_sonu_tire_kontrolu')
    # Suggest a reconstruction only if the indexed text matches the PDF lines
    # with the soft-hyphen boundary represented as a space. A visible hyphen can
    # be lexical (e.g. Perge-Side); never silently remove it.
    proposed = None
    if soft_breaks:
        source_with_boundary_space = lines[0]
        reconstructed = lines[0]
        for line in lines[1:]:
            if source_with_boundary_space.endswith('\xad'):
                source_with_boundary_space = source_with_boundary_space[:-1] + ' ' + line
                reconstructed = reconstructed[:-1] + line
            else:
                source_with_boundary_space += ' ' + line
                reconstructed += ' ' + line
        if _clean(source_with_boundary_space) == _clean(text):
            proposed = _clean(reconstructed)
        else:
            flags.append('pdf_ve_indeks_metni_farkli')
    if LOWER_START.search(text) or not TERMINAL.search(text):
        flags.append('parca_siniri_kontrolu')
    if INSTRUCTION.search(text):
        flags.append('etkinlik_veya_degerlendirme')
    if CAPTION.search(text):
        flags.append('gorsel_veya_baslik')
    if RUBRIC.search(text):
        flags.append('rubrik_kontrolu')
    if any(CITATION.search(line) for line in nearby) and not CITATION.search(text):
        flags.append('ayri_kaynak_atfi_kontrolu')
    if REFERENCE.search(text):
        flags.append('kaynakca')
    if not lines:
        flags.append('kaynak_konumu_bulunamadi')
    return {'chunk_id': item.get('chunk_id', item.get('id')), 'page': item['page'],
            'source_line_count': len(lines), 'flags': flags,
            'line_end_hyphens': [line for line in lines[:-1] if line.endswith('\xad') or re.search(r'[\wçğıöşüÇĞİÖŞÜ]-\s*$', line)],
            'proposed_soft_hyphen_text': proposed,
            'soft_hyphen_proposal_matches_index': (proposed == _clean(text)
                                                   if proposed else None)}


def holdout(index: dict, development: dict, seed: int, per_section: int) -> dict:
    if development['source_checksum'] != index['source_checksum']:
        raise ValueError('source checksum mismatch')
    # Validate the original development sample and its labels before excluding it.
    evaluate(index, development)
    excluded = {item['chunk_id'] for item in development['items']}
    groups = defaultdict(list)
    for item in index['chunks']:
        if item['id'] not in excluded:
            groups[item['section_id']].append(item)
    rng = random.Random(seed)
    items = []
    for section in sorted(groups):
        candidates = sorted(groups[section], key=lambda item: item['id'])
        for c in rng.sample(candidates, min(per_section, len(candidates))):
            items.append({'chunk_id': c['id'], 'section_id': section, 'page': c['page'],
                          'bbox': c['bbox'], 'text': c['text'], 'label': None,
                          'reviewer': None, 'source_checked': False})
    rng.shuffle(items)
    return {'schema': 'history-rag-holdout-v1', 'source_checksum': index['source_checksum'],
            'seed': seed, 'per_section': per_section, 'excluded_development_ids': len(excluded),
            'section_remaining': {k: len(v) for k, v in sorted(groups.items())}, 'items': items,
            'notice': 'Unlabeled holdout; not an approval or a training dataset.'}



def evaluate_holdout(index: dict, development: dict, reviewed: dict, pdf) -> dict:
    """Validate the predetermined holdout and compare rules on labeled items only."""
    expected = holdout(index, development, 20261025, 5)
    for key in ('schema', 'source_checksum', 'seed', 'per_section',
                'excluded_development_ids', 'section_remaining'):
        if reviewed.get(key) != expected[key]:
            raise ValueError('holdout metadata mismatch')
    originals = {x['chunk_id']: x for x in expected['items']}
    items = reviewed.get('items')
    if not isinstance(items, list) or len(items) != len(originals):
        raise ValueError('holdout size mismatch')
    seen = set()
    rows = []
    for item in items:
        identity = item.get('chunk_id')
        if identity not in originals or identity in seen:
            raise ValueError('foreign or duplicate holdout item')
        seen.add(identity)
        if any(item.get(k) != originals[identity][k] for k in ('section_id', 'page', 'bbox', 'text')):
            raise ValueError('holdout content changed')
        label = item.get('label')
        if label is None:
            if item.get('source_checked') is not False or item.get('reviewer') is not None:
                raise ValueError('unlabeled item must remain unreviewed')
            continue
        if label not in LABELS or item.get('source_checked') is not True or not isinstance(item.get('reviewer'), str) or not item['reviewer'].strip():
            raise ValueError('label requires reviewer and source check')
        rows.append((item, analyze(item, pdf[item['page'] - 1])))
    bad = sum(item['label'] in BAD for item, _ in rows)
    def scores(flag_fn):
        flagged = sum(flag_fn(item, detail) for item, detail in rows)
        tp = sum(flag_fn(item, detail) and item['label'] in BAD for item, detail in rows)
        return {'flagged': flagged, 'flagged_bad': tp,
                'precision': tp / flagged if flagged else None,
                'recall': tp / bad if bad else None}
    return {'schema': 'history-rag-holdout-report-v1', 'source_checksum': index['source_checksum'],
            'sample_size': len(items), 'labeled': len(rows), 'complete': len(rows) == len(items),
            'labels': dict(Counter(item['label'] for item, _ in rows)), 'bad': bad,
            'previous': scores(lambda item, _: bool(candidate_review_warnings(item['text']))),
            'experimental': scores(lambda _, detail: bool(detail['flags'])),
            'notice': 'Descriptive labeled-sample results, not population estimates or factual accuracy.'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--development', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--holdout', type=Path, required=True)
    parser.add_argument('--evaluate-holdout', action='store_true', help='Treat --holdout as a reviewed input')
    args = parser.parse_args()
    root = (Path(__file__).resolve().parents[4] / 'data/private').resolve()
    for target in ((args.output,) if args.evaluate_holdout else (args.output, args.holdout)):
        if not target.resolve().is_relative_to(root):
            raise ValueError('output must be in data/private')
    index = load_index(args.source, args.index)
    development = json.loads(args.development.read_text(encoding='utf-8'))
    evaluate(index, development)
    if args.evaluate_holdout:
        reviewed = json.loads(args.holdout.read_text(encoding='utf-8'))
        with pymupdf.open(args.source) as pdf:
            report = evaluate_holdout(index, development, reviewed, pdf)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False))
        return
    sample = holdout(index, development, 20261025, 5)
    with pymupdf.open(args.source) as pdf:
        details = [analyze(item, pdf[item['page'] - 1]) for item in development['items']]
    by_id = {item['chunk_id']: item for item in development['items']}
    bad = sum(item['label'] in BAD for item in development['items'])
    flagged = sum(bool(d['flags']) for d in details)
    tp = sum(bool(d['flags']) and by_id[d['chunk_id']]['label'] in BAD for d in details)
    report = {'schema': 'history-rag-layout-development-v1', 'source_checksum': index['source_checksum'],
              'development_items': len(details), 'flagged': flagged, 'flagged_bad': tp,
              'bad': bad, 'precision_on_development': tp / flagged if flagged else None,
              'recall_on_development': tp / bad if bad else None,
              'flags': dict(Counter(flag for d in details for flag in d['flags'])),
              'details': details,
              'notice': 'Exploratory development results; labels and rules are not independent. No retrieval or approval changes.'}
    for target, data in ((args.output, report), (args.holdout, sample)):
        target.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    print(json.dumps({'development': len(details), 'flagged': flagged, 'flagged_bad': tp,
                      'bad': bad, 'holdout': len(sample['items'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
