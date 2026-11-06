"""Extract clean, target-section AYT tarama candidates from the private PDF.

This is a discovery/staging step.  It keeps only structurally complete
multiple-choice questions from explicitly selected test numbers, preserves
PDF coordinates and checksum, and never reads answer keys or solutions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from ..question_bank_extract import extract_book

TEST_HEADING = re.compile(r"AYT TARAMA TESTİ[- ](\d+)", re.IGNORECASE)
TARGET_OPTIONS = {
    19: ["1.3"],
    20: ["2.1", "2.4", "2.5"],
    21: ["3.1", "3.2"],
}


def build(source: Path, *, tests: set[int] | None = None) -> dict:
    raw = source.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    selected_tests = tests or set(TARGET_OPTIONS)
    if not selected_tests <= set(TARGET_OPTIONS):
        raise ValueError("Yalnız hedef kapsam testleri seçilebilir")
    extracted = extract_book(source)
    pages = {}
    for page, context in extracted["page_contexts"].items():
        match = TEST_HEADING.search(context.get("topic") or "")
        if match:
            pages[page] = int(match.group(1))
    rows = []
    for item in extracted["questions"]:
        question = item["question"]
        page = question["source"]["page"]
        test_number = pages.get(page)
        if test_number not in selected_tests or item["issues"]:
            continue
        rows.append({
            "candidate_id": f"ogm-ayt-tarama-full:{checksum[:12]}:{page}:c{question['source']['bbox'][0]:.0f}:q{question['number']}",
            "source_kind": "ogm_ayt_tarama_private",
            "source_checksum": checksum,
            "source_name": source.name,
            "test_number": test_number,
            "page": page,
            "target_section_options": TARGET_OPTIONS[test_number],
            "issues": [],
            "question": question,
            "transcription_status": "private_teacher_review_required",
            "answer_key_accessed": False,
            "worked_explanation_accessed": False,
        })
    return {
        "schema": "ayt-target-question-candidates-v1",
        "source_checksum": checksum,
        "source_name": source.name,
        "selected_tests": sorted(selected_tests),
        "rows": rows,
        "candidate_count": len(rows),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Private target-section discovery only; PDF evidence and teacher review are mandatory.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tests", default="19,20,21")
    args = parser.parse_args()
    tests = {int(item) for item in args.tests.split(",") if item.strip()}
    result = build(args.source, tests=tests)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidate_count": result["candidate_count"], "selected_tests": result["selected_tests"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
