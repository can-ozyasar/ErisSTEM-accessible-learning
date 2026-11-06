"""Validate a source-bound agent audit of a relation-bundle retrieval queue."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DECISIONS = {"direct", "bounded_inference", "indirect", "wrong", "insufficient"}
DIAGNOSES = {"none", "retrieval_miss", "bundle_composition_miss", "target_scope_gap"}


def _queue_cards(queue_row: dict) -> dict[str, dict]:
    return {card["source_key"]: card for card in queue_row["suggestions"]}


def build(queue: dict, audit: dict) -> dict:
    if queue.get("schema") != "official-ayt-target-relation-bundle-review-queue-v1":
        raise ValueError("İlişki-demeti inceleme kuyruğu gerekli")
    if audit.get("schema") != "teacher-official-ayt-relation-bundle-audit-local12-v1":
        raise ValueError("İlişki-demeti ajan denetimi gerekli")
    for payload in (queue, audit):
        for key in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"):
            if payload.get(key) is not False:
                raise ValueError(f"{key} false olmalı")
    if audit.get("reviewer_kind") != "history_teacher_agent_v1" or audit.get("is_human_teacher_approval") is not False:
        raise ValueError("Ajan incelemesi insan öğretmen onayı diye kaydedilemez")
    audit_input = audit.get("input", {})
    if audit_input.get("queue_schema") != queue["schema"]:
        raise ValueError("Denetim doğru kuyruk şemasına bağlı değil")
    if audit_input.get("corpus_checksum") != queue.get("corpus_checksum") or audit_input.get("source_binding") != queue.get("source_binding"):
        raise ValueError("Denetim kaynak sürümüyle eşleşmiyor")

    queue_by_id = {row["candidate_id"]: row for row in queue.get("rows", [])}
    audit_rows = audit.get("records", [])
    by_id = {row.get("candidate_id"): row for row in audit_rows}
    if len(by_id) != len(audit_rows) or set(by_id) != set(queue_by_id):
        raise ValueError("Her kuyruk sorusu tam bir kez denetlenmeli")

    supported, edges = 0, 0
    for candidate_id, queue_row in queue_by_id.items():
        row = by_id[candidate_id]
        if row.get("decision") not in DECISIONS or row.get("failure_diagnosis") not in DIAGNOSES:
            raise ValueError("Denetim kararı veya hata tanısı geçersiz")
        if row.get("reviewer_kind") != "history_teacher_agent_v1" or row.get("is_human_teacher_approval") is not False:
            raise ValueError("Soru düzeyinde ajan provenance kaydı gerekli")
        if row.get("pdf_crop_checked") is not True:
            raise ValueError("Her soru için PDF kesiti kontrolü gerekli")
        for key in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"):
            if row.get(key) is not False:
                raise ValueError(f"Soru düzeyinde {key} false olmalı")
        cards = _queue_cards(queue_row)
        reviewed = row.get("reviewed_suggestions", [])
        reviewed_keys = [item.get("source_key") for item in reviewed]
        if len(reviewed_keys) != len(set(reviewed_keys)) or set(reviewed_keys) != set(cards):
            raise ValueError("Her aday PDF kesiti tam bir kez incelenmeli")
        if any(item.get("pdf_crop_checked") is not True for item in reviewed):
            raise ValueError("Her aday için PDF kesiti kontrolü gerekli")
        support_ids = set(row.get("supporting_record_ids", []))
        expected_ids = {item["record_id"] for item in reviewed if item.get("support") is True}
        if not support_ids.issubset(expected_ids) or not support_ids.issubset({card["record_id"] for card in cards.values()}):
            raise ValueError("Destek kayıtları incelenen ve destekleyici kaynak kartlarıyla eşleşmeli")
        if row["decision"] in {"direct", "bounded_inference"} and not support_ids:
            raise ValueError("Destekleyici karar için kaynak kaydı gerekli")
        if row["decision"] not in {"direct", "bounded_inference"} and support_ids:
            raise ValueError("Destekleyici olmayan karar kaynak kaydı içeremez")
        relation_edges = row.get("relation_edges", [])
        for edge in relation_edges:
            card = cards.get(edge.get("source_key"))
            if card is None or not isinstance(edge.get("quote"), str) or edge["quote"] not in card["excerpt"]:
                raise ValueError("İlişki kenarı alıntısı incelenen PDF kesitinde birebir bulunmalı")
        supported += row["decision"] in {"direct", "bounded_inference"}
        edges += len(relation_edges)
    return {
        "schema": "official-ayt-relation-bundle-audit-validation-v1",
        "corpus_checksum": queue["corpus_checksum"],
        "source_binding": queue["source_binding"],
        "question_count": len(queue_by_id),
        "supported_question_count": supported,
        "relation_edge_count": edges,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Schema and source binding validation only; it does not approve runtime RAG, graph edges or QLoRA data.",
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
