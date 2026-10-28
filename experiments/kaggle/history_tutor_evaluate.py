"""Evaluate reviewed retrieval labels and reviewed tutor outputs, with strict splits.

JSONL inputs are private. Metrics are descriptive; synthetic fixtures are not evidence
of product quality. No third-party packages are required.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path

SPLITS = {'train', 'dev', 'test'}

def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f'line {line_no}: expected object')
        rows.append(value)
    if not rows:
        raise ValueError('empty input')
    return rows

def validate(rows: list[dict]) -> None:
    ids, groups = set(), {}
    for r in rows:
        for key in ('case_id', 'question_id', 'split', 'expected_source_ids', 'retrieved_source_ids',
                    'expected_abstain', 'abstained', 'review'):
            if key not in r:
                raise ValueError(f'missing {key}')
        if not all(isinstance(r[k], str) and r[k].strip() for k in ('case_id', 'question_id')):
            raise ValueError('case_id and question_id must be nonempty strings')
        if r['case_id'] in ids: raise ValueError('duplicate case_id')
        ids.add(r['case_id'])
        if r['split'] not in SPLITS: raise ValueError('invalid split')
        group = r.get('group_id', r['question_id'])
        if not isinstance(group, str) or not group.strip(): raise ValueError('invalid group_id')
        for identifier in ('question:' + r['question_id'], 'group:' + group):
            if identifier in groups and groups[identifier] != r['split']:
                raise ValueError('question/group crosses splits')
            groups[identifier] = r['split']
        for k in ('expected_source_ids', 'retrieved_source_ids'):
            if not isinstance(r[k], list) or any(not isinstance(x, str) or not x for x in r[k]) or len(set(r[k])) != len(r[k]):
                raise ValueError(f'invalid {k}')
        for k in ('expected_abstain', 'abstained'):
            if type(r[k]) is not bool: raise ValueError(f'invalid {k}')
        if not r['expected_abstain'] and not r['expected_source_ids']:
            raise ValueError('answerable case needs reviewed relevant sources')
        review = r['review']
        if not isinstance(review, dict): raise ValueError('review must be an object')
        for key in ('grounded', 'premature_answer', 'pedagogically_useful', 'natural_turkish'):
            if type(review.get(key)) is not bool: raise ValueError(f'invalid review.{key}')

def evaluate(rows: list[dict], split: str, k: int) -> dict:
    validate(rows)
    if split not in SPLITS or k < 1: raise ValueError('invalid split or k')
    selected = [r for r in rows if r['split'] == split]
    if not selected: raise ValueError('no examples for split')
    answerable = [r for r in selected if not r['expected_abstain']]
    unanswerable = [r for r in selected if r['expected_abstain']]
    def metric(n, d): return {'numerator': n, 'denominator': d, 'value': round(n/d, 4) if d else None}
    hits = sum(bool(set(r['expected_source_ids']) & set(r['retrieved_source_ids'][:k])) for r in answerable)
    reciprocal = []
    for r in answerable:
        positive = set(r['expected_source_ids'])
        reciprocal.append(next((1/i for i, v in enumerate(r['retrieved_source_ids'][:k], 1) if v in positive), 0))
    counts = Counter(r['question_id'] for r in selected)
    return {'split': split, 'cases': len(selected), 'unique_questions': len(counts),
            'warning': 'Turn-level descriptive metrics; cluster by question for confidence intervals.',
            f'hit_at_{k}': metric(hits, len(answerable)),
            f'mrr_at_{k}': {'sum_reciprocal_ranks': round(sum(reciprocal), 4), 'denominator': len(answerable),
                             'value': round(sum(reciprocal)/len(answerable), 4) if answerable else None},
            'correct_abstention': metric(sum(r['abstained'] for r in unanswerable), len(unanswerable)),
            'unnecessary_abstention': metric(sum(r['abstained'] for r in answerable), len(answerable)),
            **{key: metric(sum(r['review'][key] for r in selected), len(selected)) for key in
               ('grounded', 'premature_answer', 'pedagogically_useful', 'natural_turkish')}}

def main():
    p = argparse.ArgumentParser(); p.add_argument('input', type=Path)
    p.add_argument('--split', choices=sorted(SPLITS), required=True); p.add_argument('--k', type=int, default=3)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); result = evaluate(read_jsonl(args.input), args.split, args.k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__': main()
