"""Record an explicit project-owner completion of the local OGM text review."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .prepare_ogm_ayt_question_review import SCHEMA


def finalize(pack: dict, reviewer: str) -> dict:
    if pack.get("schema") != SCHEMA:
        raise ValueError("OGM gerçek soru inceleme paketi şeması geçersiz")
    reviews = pack.get("reviews")
    if not isinstance(reviews, list) or not reviews or pack.get("review_count") != len(reviews):
        raise ValueError("inceleme kayıtları eksik veya sayısı uyuşmuyor")
    if not reviewer.strip():
        raise ValueError("incelemeyi tamamlayan kişi kaydı gerekli")
    finalized = json.loads(json.dumps(pack, ensure_ascii=False))
    for record in finalized["reviews"]:
        if not isinstance(record.get("id"), str) or not record["id"]:
            raise ValueError("inceleme kayıt kimliği eksik")
        record["checks"] = {
            "pdf_text_matches": True,
            "choices_complete_and_ordered": True,
            "text_only_accessible": True,
            "scope_appropriate": True,
        }
        record["notes"] = ""
        record["status"] = "project_owner_reviewed"
    finalized.update({
        "schema": "ogm-ayt-real-question-project-owner-review-v1",
        "reviewed_at": datetime.now(UTC).isoformat(),
        "reviewer": reviewer.strip(),
        "reviewer_role": "project_owner_local_review",
        "is_human_teacher_approval": False,
        "review_decision": "all_text_and_scope_checks_confirmed",
        "runtime_enabled": False,
        "answer_key_accessed": False,
        "notice": (
            "Bu kayıt proje sahibinin yerel metin/PDF incelemesini kaydeder; öğretmen onayı, "
            "cevap anahtarı doğrulaması, kaynak kullanım izni veya öğrenci yayını değildir."
        ),
    })
    return finalized


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--all-checks-confirmed", action="store_true")
    args = parser.parse_args()
    if not args.all_checks_confirmed:
        raise SystemExit("Bu işlem için --all-checks-confirmed açıkça verilmelidir")
    result = finalize(json.loads(args.input.read_text(encoding="utf-8")), args.reviewer)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"review_count": result["review_count"], "runtime_enabled": False}))


if __name__ == "__main__":
    main()
