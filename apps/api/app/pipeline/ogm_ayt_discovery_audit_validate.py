"""Validate sampled private source discovery labels and their arithmetic."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

VERDICTS = {"direct", "partial", "irrelevant", "uncertain"}
OUTCOMES = {"direct_candidate_requires_teacher_crop_review",
            "partial_only_reretrieve_or_abstain", "insufficient_abstain"}


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00ad", "")).strip().casefold()


def validate(discovery: dict, audit: dict, integrity: dict) -> dict:
    if (discovery.get("schema") != "ogm-ayt-manual-source-discovery-v1"
            or audit.get("schema") != "pilot-manual-discovery-agent-sample-v2"
            or integrity.get("schema") != "ogm-ayt-source-integrity-v1"
            or integrity.get("source_queue_schema") != discovery["schema"]
            or any(discovery.get(key) != audit.get(key) or discovery.get(key) != integrity.get(key)
                   for key in ("source_checksum", "corpus_checksum"))):
        raise ValueError("Keşif, örneklem ve PDF kaynak sürümleri eşleşmiyor")
    for flag in ("is_teacher_approval", "answer_key_accessed", "worked_explanation_accessed",
                 "runtime_enabled", "qlora_enabled"):
        if audit.get(flag) is not False:
            raise ValueError(f"Örneklemde {flag} false olmalı")
    proposals = {row["candidate_id"]: row for row in discovery["proposals"]}
    valid_crops = {item["source_key"] for item in integrity["cards"]
                   if item["crop_text_present"] and not item["needs_crop_review"]}
    reviews = audit.get("reviews", [])
    if len({row.get("candidate_id") for row in reviews}) != len(reviews):
        raise ValueError("Örneklemde soru tekrarı var")
    counts: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    for row in reviews:
        proposal = proposals.get(row.get("candidate_id"))
        if proposal is None or len(row.get("cards", [])) != len(proposal["suggestions"]):
            raise ValueError("Örneklem kartları keşif kuyruğuyla eşleşmiyor")
        if any(row.get(flag) is not False for flag in ("teacher_approved", "runtime_eligible", "qlora_eligible")):
            raise ValueError("Agent kaynak onayı veremez")
        outcome = row.get("question_level_outcome")
        if outcome not in OUTCOMES:
            raise ValueError("Soru sonucu geçersiz")
        outcomes[outcome] += 1
        for position, (card, source) in enumerate(zip(row["cards"], proposal["suggestions"]), 1):
            key = f'{source["source_checksum"]}:{source["chunk_id"]}'
            if (card.get("rank") != position or card.get("source_checksum") != source["source_checksum"]
                    or card.get("chunk_id") != source["chunk_id"] or key not in valid_crops):
                raise ValueError("Örneklem kartı PDF kaynağıyla eşleşmiyor")
            verdict = card.get("verdict")
            if verdict not in VERDICTS:
                raise ValueError("Kart kararı geçersiz")
            if verdict == "direct" and (not card.get("claim_relation")
                                        or not card.get("verbatim_quote")
                                        or _plain(card["verbatim_quote"]) not in _plain(source["text"])):
                raise ValueError("Doğrudan kanıtın ilişkisi ve birebir alıntısı gerekli")
            counts[verdict] += 1
    summary = audit.get("summary", {})
    if (summary.get("cards") != sum(counts.values())
            or any(summary.get("verdict_counts", {}).get(key, 0) != counts[key] for key in VERDICTS)
            or any(summary.get("question_outcomes", {}).get(key, 0) != outcomes[key]
                   for key in OUTCOMES)):
        raise ValueError("Örneklem özeti kartlardan yeniden hesaplanınca tutarsız")
    return {"schema": "ogm-ayt-discovery-audit-validation-v1",
            "question_count": len(reviews), "card_count": sum(counts.values()),
            "verdict_counts": dict(counts), "outcome_counts": dict(outcomes),
            "teacher_approved_count": 0, "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Agent sample source IDs and counts verified; historical relation still requires human review."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--integrity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(json.loads(args.discovery.read_text(encoding="utf-8")),
                      json.loads(args.audit.read_text(encoding="utf-8")),
                      json.loads(args.integrity.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("question_count", "card_count", "verdict_counts")}))


if __name__ == "__main__":
    main()
