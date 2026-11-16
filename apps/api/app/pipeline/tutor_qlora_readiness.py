"""Private, content-free acceptance gate for history-coach QLoRA export.

This module deliberately reports only counts and validation reasons. It does
not write prompts, source excerpts, question text, or answer keys.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ..tutor_dataset import (
    CASES,
    CONCEPT_KEYS_SOURCE,
    EARLY_ANSWER_CASES,
    TutorReviewInput,
    split_question_ids,
)

SCHEMA = "history-tutor-qlora-readiness-v1"


def assess(records: list[dict], allowed_sources_by_question: dict[str, dict[str, str]] | None = None) -> dict:
    """Return a fail-closed, content-free readiness summary for reviewed rows."""
    by_question: dict[str, dict[str, dict]] = {}
    invalid: Counter[str] = Counter()
    error_types: Counter[str] = Counter()
    case_counts: Counter[str] = Counter()
    allowed_sources_by_question = allowed_sources_by_question or {}
    for raw in records:
        try:
            row = TutorReviewInput.model_validate(raw)
            if row.question_id in allowed_sources_by_question:
                from ..tutor_dataset import validate_review_payload
                validate_review_payload(row, allowed_sources_by_question[row.question_id])
            elif not row.approved_quality():
                raise ValueError("onay kalite koşulları tamam değil")
        except (ValueError, KeyError) as error:
            invalid[str(error)] += 1
            continue
        if not row.approved_quality():
            invalid["onay kalite koşulları tamam değil"] += 1
            continue
        if row.concept_keys_source != CONCEPT_KEYS_SOURCE or not row.concept_keys:
            invalid["onaylı graf ilişkisinden sunucuda üretilmiş kavram anahtarı yok"] += 1
            continue
        existing = by_question.setdefault(row.question_id, {}).get(row.case)
        if existing is not None:
            invalid["aynı soru ve koçluk durumu birden fazla kez onaylanmış"] += 1
            continue
        by_question[row.question_id][row.case] = row.model_dump()
        error_types[row.error_type] += 1
        case_counts[row.case] += 1

    complete = {question_id: cases for question_id, cases in by_question.items() if set(cases) == set(CASES)}
    incomplete = len(by_question) - len(complete)
    if len(complete) < 120:
        invalid["120 tam onaylı soru grubu gerekli"] += 1
    selected = sorted(complete)[:120]
    concepts_by_question = {
        question_id: sorted({concept for row in cases.values() for concept in row.get("concept_keys", [])})
        for question_id, cases in complete.items()
    }
    splits: dict[str, int] = {"train": 0, "dev": 0, "sealed_test": 0}
    split_usable = False
    if len(selected) == 120:
        try:
            for split in split_question_ids(selected, concepts_by_question).values():
                splits[split] += 1
            split_usable = all(value > 0 for value in splits.values())
        except ValueError as error:
            invalid[str(error)] += 1
    return {
        "schema": SCHEMA,
        "status": "ready" if not invalid else "blocked",
        "approved_rows_seen": sum(len(items) for items in by_question.values()),
        "complete_question_groups": len(complete),
        "incomplete_question_groups": incomplete,
        "required_question_groups": 120,
        "required_examples": 720,
        "selected_split_question_groups": splits,
        "case_counts": {case: case_counts.get(case, 0) for case in CASES},
        "error_type_counts": dict(sorted(error_types.items())),
        "blocking_reasons": dict(sorted(invalid.items())),
        "guarantees": {
            "six_cases_per_selected_question": len(selected) == 120 and not invalid,
            "question_group_split_isolated": split_usable,
            "approved_source_bound_rows_only": True,
            "early_answer_cases": sorted(EARLY_ANSWER_CASES),
            "answer_keys_included": False,
            "sealed_test_exported_to_kaggle": False,
        },
        "split_strategy": "transitive_concept_components_v1",
        "notice": "Bu rapor içerik taşımaz. Hazır durumu öğretmen onayı veya kaynak onayı yerine geçmez; dışa aktarma öncesi kapıdır.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.records.read_text(encoding="utf-8"))
    records = payload["records"] if isinstance(payload, dict) else payload
    result = assess(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
