"""Merge bounded agent pre-reviews of private discovery cards, without approval."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from .ogm_ayt_discovery_audit_validate import OUTCOMES, VERDICTS
from .ogm_ayt_discovery_audit_validate import validate as validate_sample

SCHEMA = "ogm-ayt-discovery-agent-full-v1"
BATCH_OUTCOMES = {"crop_review_required_before_use": "direct_candidate_requires_teacher_crop_review",
                  "reretrieve": "partial_only_reretrieve_or_abstain",
                  "abstain": "insufficient_abstain"}


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00ad", "")).strip().casefold()


def _normalized_outcome(value: object) -> object:
    """Map the first batch's legacy names to the public pre-review names."""
    return BATCH_OUTCOMES.get(value, value)


def _assert_batch_summary(batch: dict) -> None:
    """Accept both audited batch-v2 summary layouts, but recompute every count."""
    reviews = batch["reviews"]
    verdicts = Counter(card.get("verdict") for review in reviews for card in review.get("cards", []))
    outcomes = Counter(_normalized_outcome(review.get("question_level_outcome")) for review in reviews)
    summary = batch.get("summary", {})
    declared_cards = summary.get("cards", summary.get("crop_text_present_cards"))
    if declared_cards != sum(verdicts.values()):
        raise ValueError("Ajan partisi kart sayısı kararlarından yeniden hesaplanınca tutarsız")
    declared_verdicts = summary.get("verdict_counts", summary)
    if any(declared_verdicts.get(key, 0) != verdicts[key] for key in VERDICTS):
        raise ValueError("Ajan partisi karar özeti kart kararlarıyla tutarsız")
    declared_outcomes = summary.get("question_outcomes", summary.get("outcomes", {}))
    normalized_declared = Counter({_normalized_outcome(key): value for key, value in declared_outcomes.items()})
    if any(normalized_declared[key] != outcomes[key] for key in OUTCOMES):
        raise ValueError("Ajan partisi soru özeti kart kararlarıyla tutarsız")


def _assert_unapproved_row(row: dict) -> None:
    """An agent may suggest a card, but cannot make it usable outside review."""
    if "source_approval" in row:
        if row["source_approval"] is not False:
            raise ValueError("Agent kaynak onayı veremez")
        return
    flags = ("teacher_approved", "runtime_eligible", "qlora_eligible")
    if all(flag in row for flag in flags):
        if any(row[flag] is not False for flag in flags):
            raise ValueError("Agent kartı kullanılabilir olarak işaretleyemez")
        return
    for card in row.get("cards", []):
        if any(card.get(flag) is not False for flag in flags):
            raise ValueError("Agent kartı kullanılabilir olarak işaretleyemez")


def merge(discovery: dict, integrity: dict, sample: dict, batches: list[tuple[dict, dict]]) -> dict:
    if (discovery.get("schema") != "ogm-ayt-manual-source-discovery-v1"
            or integrity.get("schema") != "ogm-ayt-source-integrity-v1"
            or integrity.get("source_queue_schema") != discovery["schema"]
            or sample.get("schema") != "pilot-manual-discovery-agent-sample-v2"):
        raise ValueError("Keşif ve ajan ön inceleme sürümleri eşleşmiyor")
    validate_sample(discovery, sample, integrity)
    for document in [integrity, sample, *(batch for _, batch in batches)]:
        if any(document.get(key) != discovery.get(key)
               for key in ("source_checksum", "corpus_checksum")):
            raise ValueError("Kaynak checksum'ı değişmiş")
    for document in [sample, *(batch for _, batch in batches)]:
        for flag in ("is_teacher_approval", "answer_key_accessed", "worked_explanation_accessed",
                     "runtime_enabled", "qlora_enabled"):
            if document.get(flag) is not False:
                raise ValueError(f"Ajan ön incelemesinde {flag} false olmalı")
    proposals = {row["candidate_id"]: row for row in discovery["proposals"]}
    crop_keys = {card["source_key"] for card in integrity["cards"]
                 if card["crop_text_present"] and not card["needs_crop_review"]}
    all_reviews = list(sample["reviews"])
    for batch_ids, batch in batches:
        if (batch_ids.get("schema") != "ogm-ayt-discovery-audit-batch-ids-v1"
                or batch.get("schema") != "ogm-ayt-discovery-agent-batch-v2"
                or any(batch_ids.get(key) != discovery.get(key)
                       for key in ("source_checksum", "corpus_checksum"))):
            raise ValueError("Ajan parti sürümü geçersiz")
        expected = batch_ids["candidate_ids"]
        if len(expected) != len(set(expected)) or {row.get("candidate_id") for row in batch["reviews"]} != set(expected):
            raise ValueError("Ajan partisi ayrılmış tüm soruları tam bir kez içermeli")
        _assert_batch_summary(batch)
        all_reviews.extend(batch["reviews"])
    if len(all_reviews) != len(proposals) or {row.get("candidate_id") for row in all_reviews} != set(proposals):
        raise ValueError("Birleşik denetim 70 soruyu tam bir kez içermeli")
    counts: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    normalized = []
    for row in all_reviews:
        proposal = proposals[row["candidate_id"]]
        cards = row.get("cards", [])
        if len(cards) != len(proposal["suggestions"]):
            raise ValueError("Soru kart sayısı kaynak kuyruğuyla eşleşmiyor")
        verdicts = []
        for position, (card, source) in enumerate(zip(cards, proposal["suggestions"]), 1):
            key = f'{source["source_checksum"]}:{source["chunk_id"]}'
            if (card.get("rank") != position or card.get("source_checksum") != source["source_checksum"]
                    or card.get("chunk_id") != source["chunk_id"] or key not in crop_keys):
                raise ValueError("Ajan kartı PDF kaynağıyla eşleşmiyor")
            verdict = card.get("verdict")
            if verdict not in VERDICTS:
                raise ValueError("Ajan kart kararı geçersiz")
            if verdict == "direct" and (not card.get("claim_relation")
                                        or not card.get("verbatim_quote")
                                        or _plain(card["verbatim_quote"]) not in _plain(source["text"])):
                raise ValueError("Doğrudan ilişki için birebir kaynak alıntısı gerekli")
            verdicts.append(verdict)
            counts[verdict] += 1
        outcome = _normalized_outcome(row.get("question_level_outcome"))
        if outcome not in OUTCOMES or ("direct" in verdicts) != (outcome == "direct_candidate_requires_teacher_crop_review"):
            raise ValueError("Soru sonucu kart kararlarıyla tutarsız")
        _assert_unapproved_row(row)
        outcomes[outcome] += 1
        normalized.append({"candidate_id": row["candidate_id"], "topic": proposal["topic"],
                           "question_level_outcome": outcome, "cards": cards})
    by_id = {row["candidate_id"]: row for row in normalized}
    return {"schema": SCHEMA, "source_checksum": discovery["source_checksum"],
            "corpus_checksum": discovery["corpus_checksum"],
            "question_count": len(normalized), "card_count": sum(counts.values()),
            "verdict_counts": dict(counts), "outcome_counts": dict(outcomes),
            "reviews": [by_id[row["candidate_id"]] for row in discovery["proposals"]],
            "is_teacher_approval": False, "answer_key_accessed": False,
            "worked_explanation_accessed": False,
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Complete private agent pre-review; label quality is sampled, not human Gold approval."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--integrity", type=Path, required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--batch-a-ids", type=Path, required=True)
    parser.add_argument("--batch-a", type=Path, required=True)
    parser.add_argument("--batch-b-ids", type=Path, required=True)
    parser.add_argument("--batch-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    report = merge(load(args.discovery), load(args.integrity), load(args.sample), [
        (load(args.batch_a_ids), load(args.batch_a)), (load(args.batch_b_ids), load(args.batch_b))])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("question_count", "card_count", "verdict_counts",
                                                   "outcome_counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
