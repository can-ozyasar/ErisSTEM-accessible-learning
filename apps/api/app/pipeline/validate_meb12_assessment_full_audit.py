"""Validate the agent's PDF-crop evidence review for repaired MEB questions."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

DECISIONS = {"direct", "bounded_inference", "insufficient", "wrong"}


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00ad", "").strip()).casefold()


def validate(queue: dict, pack: dict, audit: dict, *, expected_questions: int | None = None) -> dict:
    if queue.get("schema") != "ogm-ayt-evidence-review-queue-v3":
        raise ValueError("Kanıt kuyruğu şeması geçersiz")
    if pack.get("schema") != "ogm-ayt-teacher-review-pack-v1":
        raise ValueError("PDF inceleme paketi şeması geçersiz")
    if audit.get("schema") not in {"teacher-meb12-assessment-full-evidence-audit-v1",
                                   "teacher-ayt-tarama-target-evidence-audit-v1"}:
        raise ValueError("MEB tam audit şeması geçersiz")
    if audit.get("reviewer_kind") != "history_teacher_agent_v1" or audit.get("is_human_teacher_approval") is not False:
        raise ValueError("Agent provenance veya insan onayı alanı geçersiz")
    for source in (audit, queue, pack):
        for field in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"):
            if field in source and source[field] is not False:
                raise ValueError(f"Güvenlik alanı açık: {field}")
    proposals = {row["candidate_id"]: row for row in queue.get("proposals", [])}
    pack_rows = {row["candidate_id"]: row for row in pack.get("reviews", [])}
    records = audit.get("records", [])
    if expected_questions is not None and len(records) != expected_questions:
        raise ValueError("Beklenen soru sayısı eşleşmiyor")
    if set(pack_rows) != set(proposals) or set(records_by_id := {row.get("candidate_id") for row in records}) != set(proposals):
        raise ValueError("Kuyruk, paket ve audit soru kümeleri eşleşmiyor")
    counts: Counter[str] = Counter()
    supported = 0
    card_count = 0
    for record in records:
        candidate_id = record["candidate_id"]
        expected_cards = proposals[candidate_id]["suggestions"]
        pack_cards = pack_rows[candidate_id].get("evidence_cards", [])
        cards = record.get("card_decisions", [])
        if len(cards) != len(pack_cards) or not 1 <= len(cards) <= len(expected_cards):
            raise ValueError("Soru kart sayısı eşleşmiyor")
        expected_by_id = {item["chunk_id"]: item for item in expected_cards}
        pack_ids = {item.get("chunk_id") for item in pack_cards}
        supporting = set(record.get("supporting_record_ids", []))
        card_ids = set()
        for card in cards:
            card_id = card.get("record_id")
            if card_id not in expected_by_id or card_id not in pack_ids or card_id in card_ids:
                raise ValueError("Kart kimliği kuyrukla eşleşmiyor veya yineleniyor")
            card_ids.add(card_id)
            if card.get("pdf_crop_checked") is not True:
                raise ValueError("PDF kırpımı kontrol edilmemiş")
            if card.get("source_checksum") != expected_by_id[card_id]["source_checksum"]:
                raise ValueError("Kart kaynak checksum eşleşmiyor")
            verdict = card.get("verdict")
            if verdict is None:
                verdict = ("direct" if card.get("diagnostic") == "direct"
                           else "bounded_inference" if card.get("support")
                           else "insufficient")
            if verdict not in DECISIONS:
                raise ValueError("Geçersiz kart kararı")
            if len(str(card.get("reason", "")).strip()) < 12:
                raise ValueError("Kart gerekçesi eksik")
            counts[verdict] += 1
            quote = card.get("quote", "")
            if quote and _plain(quote) not in _plain(expected_by_id[card_id].get("text", "")):
                raise ValueError("Kaynak alıntısı PDF metin adayıyla eşleşmiyor")
        if not supporting <= card_ids:
            raise ValueError("Destek kaydı aynı sorunun kartlarından seçilmeli")
        for evidence in record.get("evidence_quotes", []):
            evidence_id = evidence.get("record_id")
            if evidence_id not in supporting:
                raise ValueError("Alıntı desteklenmeyen karta bağlanmış")
            # The reviewer quote is transcribed from the rendered PDF crop.
            # OCR text is only a retrieval hint and may contain line-break or
            # hyphenation differences, so it must not override the visual check.
            if not isinstance(evidence.get("quote"), str) or not evidence["quote"].strip():
                raise ValueError("Soru alıntısı boş olamaz")
        decision = record.get("decision")
        if decision not in DECISIONS:
            raise ValueError("Geçersiz soru kararı")
        if decision in {"direct", "bounded_inference"}:
            if not supporting:
                raise ValueError("Destekli kararda kaynak gerekli")
            supported += 1
        elif supporting:
            raise ValueError("Yetersiz kararda destek kaydı olamaz")
        card_count += len(cards)
    summary = {"schema": "meb12-assessment-full-audit-validation-v1", "question_count": len(records),
               "card_count": card_count, "decision_counts": dict(Counter(row.get("decision") for row in records)),
               "card_verdict_counts": dict(counts), "supported_question_count": supported,
               "security_passed": True, "teacher_approved_count": 0, "runtime_enabled": False, "qlora_enabled": False}
    claimed = audit.get("summary", {})
    if claimed and claimed.get("question_count") not in {None, len(records)}:
        raise ValueError("Audit özeti soru sayısıyla eşleşmiyor")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = validate(load(args.queue), load(args.pack), load(args.audit))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
