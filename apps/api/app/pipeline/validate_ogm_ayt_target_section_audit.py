"""Validate the private OGM AYT target-section evidence audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "teacher-ogm-ayt-target-section-evidence-audit-v1"
DECISIONS = {"direct", "bounded_inference", "insufficient", "wrong"}


def validate(audit: dict, *, expected_candidates: int | None = None) -> dict:
    if audit.get("schema") != SCHEMA:
        raise ValueError("OGM hedef bölüm kanıt audit şeması geçersiz")
    if audit.get("reviewer_kind") != "history_teacher_agent_v1":
        raise ValueError("Kaynak denetimi provenance geçersiz")
    for key in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled", "is_human_teacher_approval"):
        if audit.get(key) is not False:
            raise ValueError(f"Güvenlik alanı kapalı olmalı: {key}")
    records = audit.get("records", [])
    if expected_candidates is not None and len(records) != expected_candidates:
        raise ValueError("Beklenen aday sayısı ile audit sayısı eşleşmiyor")
    seen = set()
    counts = {decision: 0 for decision in DECISIONS}
    support_count = 0
    card_count = 0
    for record in records:
        candidate_id = record.get("candidate_id")
        if not candidate_id or candidate_id in seen:
            raise ValueError("Soru kimlikleri benzersiz olmalı")
        seen.add(candidate_id)
        decision = record.get("decision")
        if decision not in DECISIONS:
            raise ValueError("Geçersiz audit kararı")
        counts[decision] += 1
        cards = record.get("card_decisions", [])
        if record.get("pdf_crop_checked") is not True or any(card.get("pdf_crop_checked") is not True for card in cards):
            raise ValueError("Her audit kartı PDF kesitiyle kontrol edilmeli")
        card_count += len(cards)
        card_ids = {card.get("record_id") for card in cards}
        supporting = set(record.get("supporting_record_ids", []))
        if not supporting <= card_ids:
            raise ValueError("Destek kaydı aynı sorunun kart havuzunda olmalı")
        if decision in {"direct", "bounded_inference"}:
            if not supporting:
                raise ValueError("Desteklenen kararda kaynak kaydı gerekli")
            support_count += 1
        elif supporting:
            raise ValueError("Yetersiz kararda destek kaydı bulunamaz")
        for edge in record.get("relation_edges", []):
            if not set(edge.get("source_record_ids", [])) <= card_ids:
                raise ValueError("İlişki kenarı satır dışı kaynağa bağlanamaz")
    summary = {
        "candidate_count": len(records), "card_count": card_count,
        "decision_counts": counts, "supported_candidate_count": support_count,
        "security_passed": True,
    }
    claimed = audit.get("summary")
    if claimed and claimed.get("candidate_count") != summary["candidate_count"]:
        raise ValueError("Audit özeti aday sayısıyla uyuşmuyor")
    return {"schema": "ogm-ayt-target-section-audit-validation-v1", **summary, "source_audit_schema": SCHEMA}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-candidates", type=int)
    args = parser.parse_args()
    result = validate(json.loads(args.input.read_text(encoding="utf-8")), expected_candidates=args.expected_candidates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
