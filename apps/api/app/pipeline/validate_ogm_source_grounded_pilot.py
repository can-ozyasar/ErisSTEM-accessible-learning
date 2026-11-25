"""Validate the fail-closed, local-only source-grounded pilot candidate package."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(package: dict, review: dict, answers: dict, readiness: dict) -> dict:
    if package.get("schema") != "ogm-ayt-history-source-grounded-pilot-candidates-v1":
        raise ValueError("pilot aday paketi gerekli")
    if package.get("runtime_enabled") is not False:
        raise ValueError("aday paket çalışma zamanına açılamaz")
    if review.get("is_human_teacher_approval") is not False:
        raise ValueError("AI incelemesi insan öğretmen onayı olarak işaretlenemez")
    source = package.get("source_checksum")
    if source != answers.get("source_checksum") or source != readiness.get("source_checksum"):
        raise ValueError("soru kaynağı checksum zinciri bozuk")
    questions = package.get("questions", [])
    if package.get("candidate_count") != len(questions) or not questions:
        raise ValueError("aday sayısı boş veya tutarsız")
    ids = [row.get("candidate_id") for row in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("tekrarlı aday kimliği")
    approved = {row["id"] for row in readiness.get("approved_transcription_candidates", [])}
    answer_by_id = {row["candidate_id"]: row for row in answers.get("records", [])}
    review_by_id = {row["candidate_id"]: row for row in review.get("reviews", [])}
    maximum = package.get("maximum_evidence_items", 3)
    if not isinstance(maximum, int) or maximum < 1 or maximum > 3:
        raise ValueError("kanıt paketi sınırı 1–3 arasında olmalı")
    bundle_sizes = []
    for item in questions:
        identifier = item["candidate_id"]
        if identifier not in approved or identifier not in answer_by_id:
            raise ValueError(f"doğrulanmamış soru: {identifier}")
        if item.get("correct_choice") != answer_by_id[identifier].get("correct_choice"):
            raise ValueError(f"cevap anahtarı uyuşmazlığı: {identifier}")
        source_record = item.get("answer_key_source", {})
        if source_record.get("source_checksum") != source:
            raise ValueError(f"cevap anahtarı kaynak uyuşmazlığı: {identifier}")
        selected = item.get("evidence_bundle", [])
        if not selected or len(selected) > maximum:
            raise ValueError(f"geçersiz kanıt demeti: {identifier}")
        supported = {candidate["id"] for candidate in review_by_id.get(identifier, {}).get("candidates", [])
                     if candidate.get("verdict") == "support"}
        for evidence in selected:
            required = ("id", "source_name", "source_checksum", "page", "bbox", "excerpt")
            if any(evidence.get(key) in (None, "") for key in required) or evidence["id"] not in supported:
                raise ValueError(f"denetlenemeyen kanıt: {identifier}")
        bundle_sizes.append(len(selected))
    return {"valid": True, "candidate_count": len(questions), "maximum_evidence_items": maximum,
            "max_actual_bundle_size": max(bundle_sizes), "runtime_enabled": False,
            "notice": "Structural validation passed. This remains an AI-reviewed, local-only candidate package."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(validate(load(args.package), load(args.review), load(args.answers), load(args.readiness)), ensure_ascii=False))


if __name__ == "__main__":
    main()
