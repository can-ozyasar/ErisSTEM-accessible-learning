"""Seal batched DeepSeek semantic checks without treating them as approval."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "ayt-history-ai-semantic-review-gate-v1"
VALIDATION_SCHEMA = "deepseek-question-semantic-validation-v1"


def _checksum(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build(candidate_pack: dict, batches: list[dict]) -> dict:
    if candidate_pack.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("120 soruluk aday paketi gerekli")
    questions = candidate_pack.get("questions", [])
    if len(questions) != 120 or len({row.get("id") for row in questions}) != 120:
        raise ValueError("Aday paketi 120 benzersiz soru taşımalı")
    expected = {row["id"] for row in questions}
    candidate_checksum = candidate_pack.get("candidate_checksum")
    corpus_checksum = candidate_pack.get("corpus_checksum")
    if not isinstance(candidate_checksum, str) or not isinstance(corpus_checksum, str):
        raise TypeError("Aday kaynak checksum'ları gerekli")
    validations: dict[str, dict] = {}
    batch_signatures = []
    for batch in batches:
        if (batch.get("schema") != VALIDATION_SCHEMA
                or batch.get("candidate_checksum") != candidate_checksum
                or batch.get("corpus_checksum") != corpus_checksum):
            raise ValueError("AI denetim batch'i aday kaynak sürümüyle eşleşmiyor")
        if any(batch.get(key) is not False for key in (
            "answer_key_accessed", "student_data_accessed", "is_human_teacher_approval",
            "runtime_enabled", "qlora_enabled",
        )):
            raise ValueError("AI denetimi güvenlik bayrakları kapalı olmalı")
        rows = batch.get("validations")
        if not isinstance(rows, list) or not rows:
            raise ValueError("AI denetim batch'i boş olamaz")
        batch_signatures.append(_checksum(batch))
        for row in rows:
            identifier = row.get("id")
            if identifier not in expected or identifier in validations:
                raise ValueError("AI denetiminde eksik, yabancı veya yinelenen soru kimliği")
            if (row.get("verdict") not in {"accept_for_release_validation", "reject"}
                    or row.get("runtime_enabled") is not False):
                raise ValueError("AI denetim hükmü geçersiz")
            validations[identifier] = row
    if set(validations) != expected:
        raise ValueError("AI denetimi 120 adayın tamamını tam bir kez kapsamalı")
    accepted = sorted(identifier for identifier, row in validations.items()
                      if row["verdict"] == "accept_for_release_validation")
    held = sorted(identifier for identifier, row in validations.items() if row["verdict"] == "reject")
    return {
        "schema": SCHEMA,
        "candidate_checksum": candidate_checksum,
        "corpus_checksum": corpus_checksum,
        "question_set_checksum": _checksum(questions),
        "validation_batches_checksum": _checksum(sorted(batch_signatures)),
        "accepted_for_human_pdf_crop_review": accepted,
        "review_required": held,
        "validations": [validations[row["id"]] for row in questions],
        "summary": {"candidate_count": len(expected), "ai_accepted": len(accepted), "review_required": len(held)},
        "answer_key_accessed": False,
        "student_data_accessed": False,
        "is_human_teacher_approval": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "AI semantic gate only. Accepted entries still require independent human PDF-crop review and cannot enable runtime, RAG evidence or QLoRA.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--batch", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.candidate_pack), [load(path) for path in args.batch])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
