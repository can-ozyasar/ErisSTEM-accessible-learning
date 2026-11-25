"""Fail closed: create a pilot candidate package only from complete MEB evidence reviews."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build(review: dict, answers: dict, readiness: dict) -> dict:
    if review.get("schema") != "ogm-ayt-real-question-evidence-pdf-review-v1":
        raise ValueError("PDF kanıt inceleme kaydı gerekli")
    if answers.get("schema") != "ogm-ayt-history-answer-key-v1":
        raise ValueError("checksum bağlı cevap anahtarı gerekli")
    if readiness.get("schema") != "ogm-ayt-real-question-pilot-readiness-v1":
        raise ValueError("gerçek soru hazırlık raporu gerekli")
    source = review.get("question_source_checksum")
    if source != answers.get("source_checksum") or source != readiness.get("source_checksum"):
        raise ValueError("soru, cevap anahtarı ve hazırlık kaynak checksum değerleri uyuşmuyor")
    answer_by_id = {row["candidate_id"]: row for row in answers.get("records", [])}
    allowed = {row["id"] for row in readiness.get("approved_transcription_candidates", [])}
    # The coach may receive only a small, auditable evidence bundle.  Keeping
    # the queue ordering makes selection reproducible and avoids turning a
    # passing retrieval review into an unbounded-context prompt.
    maximum_evidence_items = 3
    selected = []
    dropped_support_count = 0
    for row in review.get("reviews", []):
        supports = [item for item in row.get("candidates", []) if item.get("verdict") == "support"]
        if row.get("abstain") is True:
            continue
        if row.get("coverage_complete") is not True or not supports:
            continue
        identifier = row.get("candidate_id")
        if identifier not in allowed or identifier not in answer_by_id:
            raise ValueError("inceleme kaydında doğrulanmamış soru kimliği")
        chosen_supports = supports[:maximum_evidence_items]
        dropped_support_count += len(supports) - len(chosen_supports)
        selected.append({"candidate_id": identifier, "correct_choice": answer_by_id[identifier]["correct_choice"],
                         "answer_key_source": answer_by_id[identifier]["answer_key_source"],
                         "evidence_bundle": [{key: item[key] for key in ("id", "source_name", "source_checksum", "page", "bbox", "excerpt")}
                                             for item in chosen_supports]})
    return {"schema": "ogm-ayt-history-source-grounded-pilot-candidates-v1", "source_checksum": source,
            "review_checksum": _digest(review), "answer_key_checksum": _digest(answers),
            "candidate_count": len(selected), "maximum_evidence_items": maximum_evidence_items,
            "dropped_supported_items": dropped_support_count, "questions": selected, "runtime_enabled": False,
            "notice": "Candidate package only. It requires a final package integrity check before any exam runtime uses answers or evidence."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.review), load(args.answers), load(args.readiness))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidate_count": result["candidate_count"], "runtime_enabled": False}))


if __name__ == "__main__":
    main()
