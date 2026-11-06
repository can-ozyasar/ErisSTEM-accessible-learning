"""Validate an agent PDF-crop audit for multi-source AYT candidate retrieval."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DECISIONS = {"direct", "bounded_inference", "indirect", "wrong", "insufficient"}
DIAGNOSES = {"none", "extraction_gap", "retrieval_miss", "bundle_composition_miss", "genuine_source_gap"}
QUEUE_SCHEMAS = {
    "official-ayt-multisource-dense-review-queue-v1",
    "official-ayt-full-multisource-dense-review-queue-v1",
    "official-ayt-full-targeted-expansion-review-queue-v1",
}
AUDIT_SCHEMAS = {
    "teacher-official-ayt-multisource-dense-audit-v1",
    "teacher-official-ayt-multisource-dense-audit-v2",
    "teacher-official-ayt-full-multisource-dense-audit-v2",
    "teacher-official-ayt-full-targeted-expansion-audit-v1",
}


def _assert_false(payload: dict) -> None:
    for key in (
        "answer_key_accessed",
        "worked_explanation_accessed",
        "runtime_enabled",
        "qlora_enabled",
    ):
        if payload.get(key) is not False:
            raise ValueError(f"{key} false olmalı")


def build(queue: dict, audit: dict) -> dict:
    if queue.get("schema") not in QUEUE_SCHEMAS:
        raise ValueError("Çok kaynaklı PDF kesiti inceleme kuyruğu gerekli")
    if audit.get("schema") not in AUDIT_SCHEMAS:
        raise ValueError("Çok kaynaklı tarih öğretmeni ajan denetimi gerekli")
    _assert_false(queue)
    _assert_false(audit)
    if audit.get("reviewer_kind") != "history_teacher_agent_v1" or audit.get("is_human_teacher_approval") is not False:
        raise ValueError("Ajan incelemesi insan öğretmen onayı diye kaydedilemez")
    audit_input = audit.get("input", {})
    if audit_input.get("queue_schema") != queue["schema"]:
        raise ValueError("Denetim doğru kuyruk şemasına bağlı değil")
    if audit_input.get("corpus_checksum") != queue["corpus_checksum"]:
        raise ValueError("Denetim corpus checksum değerine bağlı değil")
    if audit_input.get("source_bindings") != queue["source_bindings"]:
        raise ValueError("Denetim kaynak bağlarıyla eşleşmiyor")

    bindings = {item["source_checksum"] for item in queue["source_bindings"]}
    queue_rows = {row["candidate_id"]: row for row in queue.get("rows", [])}
    audit_rows = {row.get("candidate_id"): row for row in audit.get("records", [])}
    if len(audit_rows) != len(audit.get("records", [])) or set(audit_rows) != set(queue_rows):
        raise ValueError("Her kuyruk sorusu tam bir kez denetlenmeli")

    supported = 0
    checked_cards = 0
    relation_edges = 0
    for candidate_id, queue_row in queue_rows.items():
        row = audit_rows[candidate_id]
        if row.get("decision") not in DECISIONS or row.get("failure_diagnosis") not in DIAGNOSES:
            raise ValueError("Denetim kararı veya hata tanısı geçersiz")
        if row.get("reviewer_kind") != "history_teacher_agent_v1" or row.get("is_human_teacher_approval") is not False:
            raise ValueError("Soru düzeyinde ajan provenance kaydı gerekli")
        if row.get("pdf_crop_checked") is not True:
            raise ValueError("Her soru için PDF kesiti kontrolü gerekli")
        _assert_false(row)
        cards = {card["source_key"]: card for card in queue_row["suggestions"]}
        if any(card["source_checksum"] not in bindings for card in cards.values()):
            raise ValueError("Kuyrukta tanımsız kaynak checksum değeri var")
        reviewed = row.get("reviewed_suggestions", [])
        reviewed_by_key = {item.get("source_key"): item for item in reviewed}
        if len(reviewed_by_key) != len(reviewed) or set(reviewed_by_key) != set(cards):
            raise ValueError("Her aday PDF kesiti tam bir kez incelenmeli")
        if any(item.get("pdf_crop_checked") is not True for item in reviewed):
            raise ValueError("Her aday için PDF kesiti kontrolü gerekli")
        support_ids = set(row.get("supporting_record_ids", []))
        supporting_cards = {
            cards[key]["record_id"]
            for key, item in reviewed_by_key.items()
            if item.get("support") is True
        }
        if not support_ids.issubset(supporting_cards):
            raise ValueError("Destek kayıtları destekleyici olarak incelenmiş kaynaklardan gelmeli")
        if row["decision"] in {"direct", "bounded_inference"} and not support_ids:
            raise ValueError("Destekleyici karar için kaynak kaydı gerekli")
        if row["decision"] not in {"direct", "bounded_inference"} and support_ids:
            raise ValueError("Destekleyici olmayan karar kaynak kaydı içeremez")
        for edge in row.get("relation_edges", []):
            card = cards.get(edge.get("source_key"))
            quote = edge.get("quote")
            if card is None or not isinstance(quote, str) or quote not in card["excerpt"]:
                raise ValueError("İlişki kenarı alıntısı incelenen PDF kesitinde birebir bulunmalı")
        supported += row["decision"] in {"direct", "bounded_inference"}
        checked_cards += len(reviewed)
        relation_edges += len(row.get("relation_edges", []))
    return {
        "schema": "official-ayt-multisource-dense-audit-validation-v1",
        "corpus_checksum": queue["corpus_checksum"],
        "source_bindings": queue["source_bindings"],
        "question_count": len(queue_rows),
        "checked_card_count": checked_cards,
        "supported_question_count": supported,
        "relation_edge_count": relation_edges,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Schema and provenance validation only; this does not approve student RAG, graph edges, or QLoRA data.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.queue), load(args.audit))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"questions": result["question_count"], "supported": result["supported_question_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
