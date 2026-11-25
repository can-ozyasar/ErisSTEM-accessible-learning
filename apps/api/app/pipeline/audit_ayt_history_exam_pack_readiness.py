"""Audit whether an authored AYT History candidate pack may enter runtime.

This is deliberately a publication gate, not a question-quality classifier.
It never emits answer labels, question text, explanations, or source quotes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_SPLITS = {"development": 72, "retrieval_test": 24, "system_acceptance": 24}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(candidate_path: Path, split_path: Path) -> dict[str, Any]:
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    split = json.loads(split_path.read_text(encoding="utf-8"))
    if candidate.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("Aday paket şeması desteklenmiyor")
    if split.get("schema") != "ayt-history-candidate-split-v1":
        raise ValueError("Bölümleme şeması desteklenmiyor")

    questions = candidate.get("questions")
    records = split.get("records")
    if not isinstance(questions, list) or not isinstance(records, list):
        raise TypeError("Aday soru veya bölümleme kayıtları liste olmalı")
    ids = [item.get("id") for item in questions]
    if len(ids) != 120 or len(set(ids)) != 120 or not all(isinstance(item, str) for item in ids):
        raise ValueError("Yayın denetimi 120 benzersiz aday soru bekler")
    split_by_id = {item.get("id"): item.get("split") for item in records}
    if set(split_by_id) != set(ids):
        raise ValueError("Aday paketi ve dondurulmuş bölümleme aynı soru kimliklerini içermeli")
    actual_splits = Counter(split_by_id.values())
    if dict(actual_splits) != EXPECTED_SPLITS:
        raise ValueError("Bölümleme 72/24/24 olmalı")

    blockers: Counter[str] = Counter()
    eligible_ids: list[str] = []
    for question in questions:
        question_id = question["id"]
        reasons: list[str] = []
        if question.get("authorship") != "original":
            reasons.append("not_original")
        if question.get("status") != "approved":
            reasons.append("not_approved")
        if question.get("runtime_enabled") is not False:
            reasons.append("runtime_flag_invalid")
        evidence = question.get("source_evidence")
        # Candidate packs have one source_evidence object.  The runtime pack
        # will transform it into an explicit 1–3 member evidence bundle.
        evidence_items = evidence if isinstance(evidence, list) else [evidence]
        if not 1 <= len(evidence_items) <= 3:
            reasons.append("evidence_bundle_invalid")
        else:
            for item in evidence_items:
                if not isinstance(item, dict) or not all(item.get(key) for key in ("source_id", "source_checksum", "page", "bbox")):
                    reasons.append("evidence_locator_missing")
                    break
        # AI review is useful triage only; its presence cannot make a question publishable.
        if question.get("human_pdf_crop_review") is not True:
            reasons.append("human_pdf_crop_review_missing")
        if question.get("review_artifact_checksum") is None:
            reasons.append("human_review_artifact_missing")
        if reasons:
            blockers.update(reasons)
        else:
            eligible_ids.append(question_id)

    return {
        "schema": "ayt-history-exam-pack-readiness-audit-v1",
        "candidate_path": str(candidate_path),
        "candidate_file_checksum": sha256_file(candidate_path),
        "candidate_checksum": candidate.get("candidate_checksum"),
        "corpus_checksum": candidate.get("corpus_checksum"),
        "split_path": str(split_path),
        "split_file_checksum": sha256_file(split_path),
        "question_count": len(questions),
        "split_counts": dict(sorted(actual_splits.items())),
        "eligible_question_count": len(eligible_ids),
        "blocker_counts": dict(sorted(blockers.items())),
        "runtime_pack_may_be_built": len(eligible_ids) == 120,
        "answer_key_accessed": False,
        "student_data_accessed": False,
        "is_human_teacher_approval": False,
        "runtime_enabled": False,
        "notice": (
            "Bu denetim yalnız yayın ön koşullarını sayar. AI değerlendirmesi insan PDF/kaynak "
            "doğrulaması değildir; eksik onaylı adaylar öğrenci çalışma zamanına bağlanamaz."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.candidate, args.split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
