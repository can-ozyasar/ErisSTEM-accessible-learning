"""Freeze semantically validated question-bank candidates for later training work.

This deliberately does not mark Socratic/QLoRA training ready: question items
are not teacher-dialogue examples and must never be silently repurposed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _fingerprint(question: dict) -> str:
    fields = {key: question.get(key) for key in ("id", "question", "spoken_question", "choices", "correct_label", "explanation", "source_evidence")}
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build(current: dict, prior: dict, validations: list[dict]) -> dict:
    for pack in (current, prior):
        if pack.get("schema") != "ayt-history-original-question-candidate-pack-v1":
            raise ValueError("Aday soru paketi gerekli")
    if current.get("corpus_checksum") != prior.get("corpus_checksum"):
        raise ValueError("Aday paket corpus sürümleri uyuşmuyor")
    prior_fingerprints = {row["id"]: _fingerprint(row) for row in prior.get("questions", [])}
    accepted: dict[tuple[str, str], dict] = {}
    for batch in validations:
        if batch.get("schema") != "deepseek-question-semantic-validation-v1" or batch.get("corpus_checksum") != current.get("corpus_checksum"):
            raise ValueError("Semantik denetim sürümü veya corpus uyuşmuyor")
        checksum = batch.get("candidate_checksum")
        if checksum not in {current.get("candidate_checksum"), prior.get("candidate_checksum")}:
            raise ValueError("Semantik denetim bilinmeyen aday paketine ait")
        for row in batch.get("validations", []):
            key = (checksum, row.get("id"))
            if key in accepted:
                raise ValueError("Aynı aday için tekrarlı semantik denetim")
            if row.get("verdict") == "accept_for_release_validation":
                accepted[key] = row
    final_rows = []
    for question in current.get("questions", []):
        identifier = question.get("id")
        current_key = (current["candidate_checksum"], identifier)
        prior_key = (prior["candidate_checksum"], identifier)
        valid_current = current_key in accepted
        unchanged_prior = prior_fingerprints.get(identifier) == _fingerprint(question) and prior_key in accepted
        if not (valid_current or unchanged_prior):
            raise ValueError(f"Semantik olarak kabul edilmiş kapsam eksik: {identifier}")
        if question.get("status") != "source_crop_validation_required" or question.get("runtime_enabled") is not False:
            raise ValueError("Kapanmamış kaynak veya runtime durumu")
        final_rows.append({**question, "status": "question_bank_training_candidate", "runtime_enabled": False})
    frozen_checksum = hashlib.sha256(json.dumps(final_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"schema": "ayt-history-question-bank-training-candidate-v1", "corpus_checksum": current["corpus_checksum"],
            "candidate_checksum": current["candidate_checksum"], "frozen_checksum": frozen_checksum, "questions": final_rows,
            "summary": {"question_count": len(final_rows), "semantic_validation_coverage": len(final_rows),
                        "question_bank_training_candidate_ready": True, "qlora_training_ready": False},
            "answer_key_accessed": False, "student_data_accessed": False, "runtime_enabled": False,
            "question_bank_training_candidate_ready": True, "qlora_training_ready": False,
            "notice": "Ready only as a private question-bank training candidate. It is not a Socratic coaching/QLoRA dataset and is not runtime-released."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-pack", type=Path, required=True)
    parser.add_argument("--prior-pack", type=Path, required=True)
    parser.add_argument("--validation", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.current_pack), load(args.prior_pack), [load(path) for path in args.validation])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
