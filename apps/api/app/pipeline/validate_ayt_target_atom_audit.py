"""Validate the PDF-crop audit for the scoped official AYT atom queue.

The audit is an agent review aid.  Passing this validator never approves a
source for runtime RAG or QLoRA; it only proves row-local provenance and crop
coverage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DECISIONS = {"direct", "bounded_inference", "indirect", "insufficient", "wrong"}


def _false(payload: dict) -> None:
    for key in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"):
        if payload.get(key) is not False:
            raise ValueError(f"{key} false olmalı")


def build(proposals: dict, audit: dict) -> dict:
    if proposals.get("schema") != "ayt-evidence-proposals-v1":
        raise ValueError("Atom/bağlam öneri şeması gerekli")
    if audit.get("schema") != "teacher-official-ayt-target-atom-audit-v2":
        raise ValueError("Sürümlü hedef atom audit şeması gerekli")
    _false(proposals)
    _false(audit)
    if audit.get("reviewer_kind") != "history_teacher_agent_v1" or audit.get("is_human_teacher_approval") is not False:
        raise ValueError("Ajan provenance kaydı gerekli; insan onayı iddia edilemez")
    proposal_rows = {row["candidate_id"]: row for row in proposals.get("proposals", [])}
    audit_rows = {row.get("candidate_id"): row for row in audit.get("records", [])}
    if len(audit_rows) != len(audit.get("records", [])) or set(audit_rows) != set(proposal_rows):
        raise ValueError("Her aday tam bir kez denetlenmeli")

    checked_cards = 0
    supported = 0
    edge_count = 0
    decisions = {key: 0 for key in DECISIONS}
    for candidate_id, proposal in proposal_rows.items():
        row = audit_rows[candidate_id]
        if row.get("decision") not in DECISIONS:
            raise ValueError("Geçersiz soru kararı")
        if row.get("reviewer_kind") != "history_teacher_agent_v1" or row.get("is_human_teacher_approval") is not False:
            raise ValueError("Soru provenance kaydı eksik")
        if row.get("pdf_crop_checked") is not True:
            raise ValueError("PDF kesiti kontrol edilmemiş")
        _false(row)
        suggestions = {item["record_id"]: item for item in proposal.get("suggestions", [])}
        cards = row.get("card_decisions", [])
        if len(cards) != len(proposal.get("suggestions", [])):
            raise ValueError("Aday kartlarının tamamı incelenmeli")
        card_ids = {item.get("record_id") for item in cards}
        if card_ids != set(suggestions):
            raise ValueError("Kart record_id kümesi öneriyle eşleşmiyor")
        if any(item.get("pdf_crop_checked") is not True for item in cards):
            raise ValueError("Her kartın PDF kesiti kontrol edilmeli")
        support_ids = set(row.get("supporting_record_ids", []))
        reviewed_support = {item["record_id"] for item in cards if item.get("support") is True}
        if not support_ids <= reviewed_support:
            raise ValueError("Destek kaydı desteklenmiş karttan gelmeli")
        if row["decision"] in {"direct", "bounded_inference"} and not support_ids:
            raise ValueError("Destek kararı kaynak kaydı gerektirir")
        if row["decision"] not in {"direct", "bounded_inference"} and support_ids:
            raise ValueError("Desteksiz kararda supporting_record_ids olamaz")
        for edge in row.get("relation_edges", []):
            edge_ids = set(edge.get("source_record_ids", []))
            if not edge_ids or not edge_ids <= support_ids:
                raise ValueError("İlişki kenarı satır içi destek kümesine bağlı değil")
        decisions[row["decision"]] += 1
        supported += row["decision"] in {"direct", "bounded_inference"}
        checked_cards += len(cards)
        edge_count += len(row.get("relation_edges", []))
    return {
        "schema": "official-ayt-target-atom-audit-validation-v1",
        "corpus_checksum": proposals.get("corpus_checksum"),
        "candidate_count": len(proposal_rows),
        "checked_card_count": checked_cards,
        "supported_candidate_count": supported,
        "decision_counts": decisions,
        "relation_edge_count": edge_count,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Provenance validation only; no runtime or QLoRA approval.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.proposals.read_text(encoding="utf-8")),
                   json.loads(args.audit.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidates": result["candidate_count"], "supported": result["supported_candidate_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
