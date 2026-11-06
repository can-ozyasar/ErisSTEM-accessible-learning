"""Validate the private, repaired 1.3 MEB assessment evidence audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DECISIONS = {"direct", "bounded_inference", "insufficient", "wrong"}


def validate(audit: dict, *, expected_questions: int = 6) -> dict:
    if audit.get("schema") != "teacher-meb12-assessment-1.3-evidence-audit-v1":
        raise ValueError("1.3 audit şeması geçersiz")
    if audit.get("reviewer_kind") != "history_teacher_agent_v1" or audit.get("is_human_teacher_approval") is not False:
        raise ValueError("Agent provenance veya insan onayı geçersiz")
    for key in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"):
        if audit.get(key) is not False:
            raise ValueError(f"Güvenlik alanı kapalı olmalı: {key}")
    records = audit.get("records", [])
    if len(records) != expected_questions:
        raise ValueError("Beklenen 1.3 soru sayısı eşleşmiyor")
    seen = set(); counts = {key: 0 for key in DECISIONS}; cards = 0; supported = 0
    for record in records:
        qid = record.get("candidate_id") or record.get("question_id")
        if not qid or qid in seen:
            raise ValueError("Soru kimlikleri benzersiz olmalı")
        seen.add(qid)
        decision = record.get("decision")
        if decision not in DECISIONS:
            raise ValueError("Geçersiz karar")
        counts[decision] += 1
        card_rows = record.get("card_decisions", [])
        if record.get("pdf_crop_checked") is not True or len(card_rows) != 3:
            raise ValueError("Her 1.3 sorusunda üç kontrol edilmiş PDF kartı gerekli")
        cards += len(card_rows)
        ids = {card.get("record_id") for card in card_rows}
        supporting = set(record.get("supporting_record_ids", []))
        if not supporting <= ids:
            raise ValueError("Destek kaydı aynı sorunun kartlarından seçilmeli")
        if decision in {"direct", "bounded_inference"}:
            if not supporting: raise ValueError("Destekli kararda kaynak gerekli")
            supported += 1
        elif supporting:
            raise ValueError("Yetersiz kararda destek kaydı olamaz")
        if any(card.get("pdf_crop_checked") is not True for card in card_rows):
            raise ValueError("PDF kesit kontrolü eksik")
        sections = record.get("target_section_decision", {}).get("sections", [])
        if sections != ["1.3"]:
            raise ValueError("1.3 adayı başka bölüme taşınmış")
    summary = {"question_count": len(records), "card_count": cards, "decision_counts": counts, "supported_question_count": supported, "security_passed": True}
    claimed = audit.get("summary", {})
    if claimed.get("question_count") != len(records) or claimed.get("card_count") != cards:
        raise ValueError("Audit özeti kayıtlarla eşleşmiyor")
    return {"schema": "meb12-assessment-1.3-audit-validation-v1", **summary}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); result = validate(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"); print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__": main()
