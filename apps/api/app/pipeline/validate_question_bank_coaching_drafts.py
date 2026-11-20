"""Fail-closed structural and leakage audit for question-bank coaching drafts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ..tutor_dataset import CASES
from ..tutor_coach import ANSWER_LABEL


def validate(payload: dict) -> dict:
    if payload.get("schema") != "ayt-history-source-bound-coaching-drafts-v1":
        raise ValueError("Kaynak bağlı koçluk taslakları gerekli")
    violations = []
    records = payload.get("records", [])
    if len(records) != 120:
        violations.append({"question_id": None, "reason": "not_exactly_120_question_groups"})
    ids = set()
    for record in records:
        identifier, turns = record.get("question_id"), record.get("turns", [])
        if not isinstance(identifier, str) or identifier in ids:
            violations.append({"question_id": identifier, "reason": "invalid_or_duplicate_question_id"})
            continue
        ids.add(identifier)
        if len(turns) != len(CASES) or [turn.get("case") for turn in turns] != list(CASES):
            violations.append({"question_id": identifier, "reason": "invalid_case_sequence"})
            continue
        for turn in turns:
            text = turn.get("guide_response", "")
            if (not isinstance(text, str) or text.count("?") != 1 or not text.endswith("?")
                    or ANSWER_LABEL.search(text) or not turn.get("source_ids") or not turn.get("evidence_quotes")
                    or turn.get("early_answer_disclosed") is not False or turn.get("runtime_enabled") is not False):
                violations.append({"question_id": identifier, "case": turn.get("case"), "reason": "unsafe_or_ungrounded_turn"})
    return {"schema": "ayt-history-source-bound-coaching-draft-audit-v1", "corpus_checksum": payload["corpus_checksum"],
            "question_bank_checksum": payload["question_bank_checksum"], "question_groups": len(records),
            "turns_checked": sum(len(row.get("turns", [])) for row in records), "violation_count": len(violations),
            "violations": violations, "accepted": not violations, "runtime_enabled": False,
            "notice": "Structural audit only; independent teacher-style review is still required before QLoRA preparation."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"accepted": result["accepted"], "violations": result["violation_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
