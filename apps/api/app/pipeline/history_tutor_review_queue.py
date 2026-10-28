"""Prepare local review candidates. Never creates approvals or training labels."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from ..history_rag import load_index, matching_sections, retrieve
from ..question_bank_extract import extract_book
from ..question_bank_routes import _layout_contaminated


def build_queue(book: dict, index: dict, per_section: int = 5) -> dict:
    if per_section < 1 or per_section > 100:
        raise ValueError('per_section must be between 1 and 100')
    counts: Counter = Counter()
    cases = []
    ids = {chunk['id'] for chunk in index['chunks']}
    for item in book['questions']:
        q = item['question']
        if item['issues'] or _layout_contaminated(q) or q.get('visuals'):
            continue
        page = q['source']['page']
        topic = (book['page_contexts'].get(page) or {}).get('topic')
        sections = matching_sections(index, topic)
        if len(sections) != 1 or counts[sections[0]] >= per_section:
            continue
        query = ' '.join(part.get('text', '') for part in q['parts'])
        candidates = retrieve(index, ids, topic, query, limit=5)
        if not candidates:
            continue
        public = {key: value for key, value in q.items() if key not in ('answer_label', 'answer_source_checked')}
        cases.append({'question_id': q['id'], 'question': public, 'topic': topic,
                      'section_id': sections[0], 'candidate_source_ids': [c['id'] for c in candidates],
                      'candidate_sources': [{k: c[k] for k in ('id', 'page', 'bbox', 'text')} for c in candidates],
                      'review_status': 'pending', 'relevant_source_ids': [],
                      'question_source_checked': False, 'source_facts_checked': False,
                      'expected_behavior': None, 'teacher_tutor_response': None})
        counts[sections[0]] += 1
    return {'schema': 'history-tutor-review-queue-v1',
            'purpose': 'Unapproved candidates for local expert review only; not training or evaluation labels.',
            'question_source_checksum': book['source_checksum'], 'evidence_source_checksum': index['source_checksum'],
            'per_section_limit': per_section, 'section_counts': dict(counts), 'cases': cases}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--question-pdf', type=Path, required=True)
    p.add_argument('--evidence-pdf', type=Path, required=True)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--per-section', type=int, default=5)
    a = p.parse_args()
    private = (Path(__file__).resolve().parents[4] / 'data/private').resolve()
    target = a.output.resolve()
    if not target.is_relative_to(private):
        raise ValueError('output must be under data/private')
    if target.exists(): raise FileExistsError('refusing to overwrite review work')
    index = load_index(a.evidence_pdf, a.index)
    book = extract_book(a.question_pdf)
    queue = build_queue(book, index, a.per_section)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    print(json.dumps({'cases': len(queue['cases']), 'sections': queue['section_counts'],
                      'status': 'pending_review', 'output_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))

if __name__ == '__main__': main()
