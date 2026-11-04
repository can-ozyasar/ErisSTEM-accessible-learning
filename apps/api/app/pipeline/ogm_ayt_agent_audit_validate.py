"""Validate an independent agent's private source judgments without approving them."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from .ogm_ayt_retrieval_gold import source_key

SCHEMA = "ogm-ayt-full-agent-audit-v1"
VERDICTS = {"direct", "partial", "irrelevant", "uncertain"}


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00ad", "")).strip().casefold()


def validate(queue: dict, audit: dict, integrity: dict) -> dict:
    if (queue.get("schema") != "ogm-ayt-evidence-review-queue-v3"
            or audit.get("schema") != SCHEMA
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
    integrity_keys = {row["source_key"] for row in integrity.get("cards", [])
                      if not row.get("needs_crop_review") and row.get("crop_text_present")}
    totals: Counter[str] = Counter()
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
            if source_key(source) not in integrity_keys:
                raise ValueError("PDF kırpımı doğrulanmamış kaynak kartı")
            verdict = card.get("verdict")
            if verdict not in VERDICTS or len(str(card.get("reason", "")).strip()) < 12:
                raise ValueError("Agent kararı veya gerekçesi eksik")
            quote = card.get("quote", "")
            if verdict == "direct" and (not quote or _plain(quote) not in _plain(source["text"])):
                raise ValueError("Doğrudan kanıt alıntısı kaynak metninde birebir bulunmalı")
            totals[verdict] += 1
        questions_with_direct += any(card["verdict"] == "direct" for card in cards)
    return {
        "schema": "ogm-ayt-agent-audit-validation-v1",
        "source_checksum": queue["source_checksum"],
        "corpus_checksum": queue["corpus_checksum"],
        "question_count": len(reviewed), "card_count": sum(totals.values()),
        "verdict_counts": dict(totals), "questions_with_direct_lead": questions_with_direct,
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
    print(json.dumps({key: result[key] for key in ("question_count", "card_count", "verdict_counts",
                                                   "questions_with_direct_lead")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
