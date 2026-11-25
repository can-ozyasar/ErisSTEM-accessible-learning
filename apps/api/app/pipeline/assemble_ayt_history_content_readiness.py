"""Assemble answer-free publication-readiness status for AYT candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build(candidate: dict[str, Any], semantic: dict[str, Any], crop_audit: dict[str, Any], human_template: dict[str, Any],
          ai_pdf_review: dict[str, Any]) -> dict[str, Any]:
    if candidate.get("schema") != "ayt-history-original-question-candidate-pack-v1" or len(candidate.get("questions", [])) != 120:
        raise ValueError("Tam 120 aday soru gerekli")
    checksum = candidate.get("candidate_checksum")
    if (not isinstance(checksum, str) or semantic.get("candidate_checksum") != checksum
            or human_template.get("candidate_checksum") != checksum or ai_pdf_review.get("candidate_checksum") != checksum):
        raise ValueError("Aday checksum'ı semantic ve insan inceleme artefaktlarıyla eşleşmeli")
    if crop_audit.get("schema") != "ayt-history-candidate-pdf-crop-text-audit-v1":
        raise ValueError("PDF crop metin denetimi gerekli")
    questions = {row["id"]: row for row in candidate["questions"]}
    semantic_rows = {row["id"]: row for row in semantic.get("validations", [])}
    crop_rows = {row["id"]: row for row in crop_audit.get("records", [])}
    human_rows = {row["id"]: row for row in human_template.get("reviews", [])}
    ai_pdf_rows = {row["id"]: row for row in ai_pdf_review.get("reviews", [])}
    if not (set(questions) == set(semantic_rows) == set(crop_rows) == set(human_rows) == set(ai_pdf_rows)):
        raise ValueError("Dört içerik artefaktı aynı 120 kimliği kapsamalı")
    records = []
    counts: Counter[str] = Counter()
    for identifier in sorted(questions):
        source_status = crop_rows[identifier].get("status")
        semantic_ok = semantic_rows[identifier].get("verdict") == "accept_for_release_validation"
        ai_pdf_ok = ai_pdf_rows[identifier].get("verdict") == "accept_for_human_confirmation"
        if source_status == "pdf_crop_text_verified" and semantic_ok and ai_pdf_ok:
            tier, action = "ai_prevalidated", "human_pdf_crop_confirmation"
        else:
            tier, action = "review_required", "human_pdf_crop_and_question_review"
        counts[tier] += 1
        records.append({"id": identifier, "source_crop_status": source_status, "semantic_verdict": semantic_rows[identifier].get("verdict"),
                        "ai_pdf_verdict": ai_pdf_rows[identifier].get("verdict"), "human_review_status": human_rows[identifier].get("status"), "readiness_tier": tier,
                        "next_action": action})
    return {"schema": "ayt-history-content-readiness-v1", "candidate_checksum": checksum,
            "corpus_checksum": candidate.get("corpus_checksum"), "candidate_question_set_checksum": _digest(candidate["questions"]),
            "inputs": {"semantic_checksum": _digest(semantic), "crop_audit_checksum": _digest(crop_audit),
                       "human_template_checksum": _digest(human_template), "ai_pdf_review_checksum": _digest(ai_pdf_review)}, "records": records,
            "summary": {"question_count": len(records), **dict(sorted(counts.items()))},
            "answer_key_accessed": False, "student_data_accessed": False, "is_human_teacher_approval": False,
            "runtime_enabled": False,
            "notice": "AI/PDF readiness triage only. Every item still requires independent human PDF-crop confirmation before it can enter a student runtime pack."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--semantic", type=Path, required=True)
    parser.add_argument("--crop-audit", type=Path, required=True)
    parser.add_argument("--human-template", type=Path, required=True)
    parser.add_argument("--ai-pdf-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.candidate), load(args.semantic), load(args.crop_audit), load(args.human_template), load(args.ai_pdf_review))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
