"""Validate a completed rank-blind PDF review against its immutable template."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

SCHEMA = "ayt-history-rank-blind-pdf-retrieval-review-template-v1"
CARD_DECISIONS = {"relevant", "wrong", "insufficient"}
CASE_DECISIONS = {"sufficient", "insufficient", "review_required"}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate(template: dict, completed: dict) -> dict:
    if template.get("schema") != SCHEMA or completed.get("schema") != SCHEMA:
        raise ValueError("Rank-blind PDF inceleme şablonu gerekli")
    for field in ("candidate_checksum", "corpus_checksum", "split_checksum", "source_catalog_checksum"):
        if completed.get(field) != template.get(field):
            raise ValueError("Tamamlanan inceleme şablon kaynak bağlarıyla eşleşmiyor")
    template_rows = {row.get("id"): row for row in template.get("reviews", [])}
    completed_rows = {row.get("id"): row for row in completed.get("reviews", [])}
    if len(template_rows) != 24 or set(template_rows) != set(completed_rows):
        raise ValueError("Tamamlanan inceleme tam 24 özgün kilitli soruyu kapsamalı")
    results, card_counts, case_counts = [], Counter(), Counter()
    for identifier in sorted(template_rows):
        original, row = template_rows[identifier], completed_rows[identifier]
        if row.get("question") != original.get("question") or row.get("choices") != original.get("choices"):
            raise ValueError("Soru veya şık metni inceleme şablonundan değiştirilemez")
        original_cards = {card.get("source_key"): card for card in original.get("cards", [])}
        cards = {card.get("source_key"): card for card in row.get("cards", [])}
        if len(original_cards) != 3 or set(original_cards) != set(cards):
            raise ValueError("Her soru için aynı üç kaynak kartı gerekli")
        if not isinstance(row.get("reviewer"), str) or not row["reviewer"].strip() or not _valid_timestamp(row.get("reviewed_at")):
            raise ValueError("İncelemeci kimliği ve ISO-8601 inceleme zamanı gerekli")
        decisions = []
        for source_key, original_card in original_cards.items():
            card = cards[source_key]
            for field in ("source_checksum", "atom_id", "page", "bbox", "crop", "excerpt"):
                if card.get(field) != original_card.get(field):
                    raise ValueError("Kaynak kartı provenance veya metni değiştirilemez")
            decision, rationale = card.get("decision"), card.get("rationale")
            if decision not in CARD_DECISIONS or not isinstance(rationale, str) or len(rationale.strip()) < 12:
                raise ValueError("Her kartta geçerli karar ve en az 12 karakterlik PDF gerekçesi gerekli")
            decisions.append(decision)
            card_counts[decision] += 1
        case_decision = row.get("case_decision")
        if case_decision not in CASE_DECISIONS:
            raise ValueError("Her soru için geçerli vaka kararı gerekli")
        if case_decision == "sufficient" and "relevant" not in decisions:
            raise ValueError("Yeterli vaka en az bir relevant kart gerektirir")
        if case_decision == "insufficient" and "relevant" in decisions:
            raise ValueError("Relevant kart içeren vaka insufficient olamaz")
        case_counts[case_decision] += 1
        results.append({"id": identifier, "case_decision": case_decision, "card_decisions": decisions})
    for field in ("answer_key_accessed", "worked_explanation_accessed", "reference_atom_accessed", "runtime_enabled", "qlora_enabled"):
        if completed.get(field) is not False:
            raise ValueError("İnceleme güvenlik alanları false kalmalı")
    return {"schema": "ayt-history-rank-blind-pdf-retrieval-review-validation-v1",
            "template_checksum": _digest(template), "completed_checksum": _digest(completed),
            "candidate_checksum": template["candidate_checksum"], "corpus_checksum": template["corpus_checksum"],
            "split_checksum": template["split_checksum"], "review_count": len(results), "results": results,
            "summary": {"card_decisions": dict(sorted(card_counts.items())), "case_decisions": dict(sorted(case_counts.items()))},
            "is_human_teacher_approval": False, "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Structural validation only. It verifies a completed rank-blind PDF review, but does not attest reviewer expertise or publish/enable runtime retrieval."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--completed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = validate(load(args.template), load(args.completed))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
