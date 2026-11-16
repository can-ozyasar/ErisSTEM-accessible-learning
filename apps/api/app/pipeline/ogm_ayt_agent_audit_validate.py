"""Validate an independent agent's private source judgments without approving them."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from .ogm_ayt_retrieval_gold import source_key

SCHEMA = "ogm-ayt-full-agent-audit-v1"
AUDIT_SCHEMAS = {
    SCHEMA,
    "ogm-ayt-retrieval-v2-independent-agent-review-v1",
    "ogm-ayt-combined-agent-audit-v1",
    "ogm-ayt-claimwise-combined-audit-v1",
}
VERDICTS = {"direct", "partial", "irrelevant", "uncertain"}
BUNDLE_DECISIONS = {"direct", "bounded_inference", "insufficient", "wrong"}


def _plain(value: str) -> str:
    value = value.replace("\u00ad", "").replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", value).strip().casefold()


def validate(queue: dict, audit: dict, integrity: dict) -> dict:
    if (queue.get("schema") != "ogm-ayt-evidence-review-queue-v3"
            or audit.get("schema") not in AUDIT_SCHEMAS
            or integrity.get("schema") != "ogm-ayt-source-integrity-v1"):
        raise ValueError("Sürümlü kanıt kuyruğu, agent denetimi ve PDF kontrolü gerekli")
    if any(audit.get(key) != queue.get(key) or integrity.get(key) != queue.get(key)
           for key in ("source_checksum", "corpus_checksum")):
        raise ValueError("Soru veya MEB corpus checksum'ı eşleşmiyor")
    if integrity.get("source_queue_schema") != queue["schema"]:
        raise ValueError("PDF kontrolü farklı bir kaynak kuyruğuna ait")
    for flag in ("is_teacher_approval", "answer_key_accessed", "worked_explanation_accessed",
                 "runtime_enabled", "qlora_enabled"):
        if audit.get(flag) is not False:
            raise ValueError(f"Agent denetiminde {flag} false olmalı")
    proposals = {row["candidate_id"]: row for row in queue.get("proposals", [])}
    reviewed = audit.get("reviews", [])
    if len(reviewed) != len(proposals) or {row.get("candidate_id") for row in reviewed} != set(proposals):
        raise ValueError("Agent denetimi bütün soruları tam bir kez kapsamalı")
    integrity_cards = {row["source_key"]: row for row in integrity.get("cards", [])}
    totals: Counter[str] = Counter()
    bundle_totals: Counter[str] = Counter()
    consistency_flags: list[dict] = []
    questions_with_direct = 0
    for row in reviewed:
        proposal = proposals[row["candidate_id"]]
        expected = proposal.get("suggestions", [])
        cards = row.get("cards", [])
        if len(cards) != len(expected):
            raise ValueError("Her soru için tüm aday kartları değerlendirilmeli")
        for card, source in zip(cards, expected):
            if (card.get("source_checksum") != source["source_checksum"]
                    or card.get("chunk_id") != source["chunk_id"]):
                raise ValueError("Agent kartı öneri sırası veya kaynak kimliğiyle eşleşmiyor")
            crop_check = integrity_cards.get(source_key(source))
            if crop_check is None or not crop_check.get("crop_text_present"):
                raise ValueError("PDF kırpımı doğrulanmamış kaynak kartı")
            verdict = card.get("verdict")
            if verdict not in VERDICTS or len(str(card.get("reason", "")).strip()) < 12:
                raise ValueError("Agent kararı veya gerekçesi eksik")
            if crop_check.get("needs_crop_review") and (
                card.get("crop_visual_checked") is not True
                or len(str(card.get("crop_visual_note", "")).strip()) < 12
            ):
                raise ValueError("Düşük OCR eşleşmeli kart için görsel PDF kontrolü gerekli")
            quote = card.get("quote", "")
            if verdict == "direct" and (not quote or _plain(quote) not in _plain(source["text"])):
                raise ValueError("Doğrudan kanıt alıntısı kaynak metninde birebir bulunmalı")
            totals[verdict] += 1
        questions_with_direct += any(card["verdict"] == "direct" for card in cards)
        bundle = row.get("bundle_assessment")
        if not isinstance(bundle, dict) or bundle.get("decision") not in BUNDLE_DECISIONS:
            raise ValueError("Her soru için doğrudan veya çoklu kanıt demeti kararı gerekli")
        if len(str(bundle.get("reason", "")).strip()) < 12:
            raise ValueError("Kanıt demeti kararı için açıklayıcı gerekçe gerekli")
        supporting_ids = bundle.get("supporting_chunk_ids")
        if not isinstance(supporting_ids, list) or len(supporting_ids) > 3:
            raise ValueError("Kanıt demeti en çok üç kaynak parçası içerebilir")
        by_id = {card["chunk_id"]: card for card in cards}
        if len(set(supporting_ids)) != len(supporting_ids) or any(item not in by_id for item in supporting_ids):
            raise ValueError("Kanıt demeti kimlikleri bu sorunun adaylarıyla eşleşmeli")
        if bundle["decision"] in {"direct", "bounded_inference"} and not supporting_ids:
            raise ValueError("Destek kararı için en az bir kaynak parçası gerekli")
        if bundle["decision"] == "direct" and not any(
            by_id[item]["verdict"] == "direct" for item in supporting_ids
        ):
            consistency_flags.append({
                "candidate_id": row["candidate_id"],
                "kind": "direct_bundle_uses_no_direct_card",
                "supporting_chunk_ids": supporting_ids,
            })
        if bundle["decision"] == "bounded_inference" and not all(
            by_id[item]["verdict"] in {"direct", "partial"} for item in supporting_ids
        ):
            raise ValueError("Sınırlı çıkarım yalnız ilgili kanıt kartlarına dayanabilir")
        bundle_totals[bundle["decision"]] += 1
    return {
        "schema": "ogm-ayt-agent-audit-validation-v1",
        "source_checksum": queue["source_checksum"],
        "corpus_checksum": queue["corpus_checksum"],
        "question_count": len(reviewed), "card_count": sum(totals.values()),
        "verdict_counts": dict(totals), "questions_with_direct_lead": questions_with_direct,
        "bundle_decision_counts": dict(bundle_totals),
        "questions_with_supported_bundle": bundle_totals["direct"] + bundle_totals["bounded_inference"],
        "bundle_consistency_passed": not consistency_flags,
        "bundle_consistency_flags": consistency_flags,
        "teacher_approved_count": 0, "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Agent pre-review passed structural/PDF checks only. Historical relation and source approval remain unverified by a human teacher.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--integrity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(json.loads(args.queue.read_text(encoding="utf-8")),
                      json.loads(args.audit.read_text(encoding="utf-8")),
                      json.loads(args.integrity.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "question_count", "card_count", "verdict_counts", "questions_with_direct_lead",
        "bundle_decision_counts", "questions_with_supported_bundle", "bundle_consistency_passed",
        "bundle_consistency_flags",
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
