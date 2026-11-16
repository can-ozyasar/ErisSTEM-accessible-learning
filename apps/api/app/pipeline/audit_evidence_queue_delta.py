"""Compare two private retrieval slates without treating overlap as relevance."""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def _signature(card: dict[str, Any]) -> tuple[str, int, tuple[float, ...]]:
    return (
        str(card["source_checksum"]),
        int(card["page"]),
        tuple(round(float(value), 2) for value in card["bbox"]),
    )


def compare(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if baseline.get("corpus_checksum") != candidate.get("corpus_checksum"):
        raise ValueError("Retrieval kuyruğu corpus checksum'ları aynı olmalı")
    if baseline.get("source_checksum") != candidate.get("source_checksum"):
        raise ValueError("Retrieval kuyruğu soru kaynağı checksum'ları aynı olmalı")
    old_rows = {row["candidate_id"]: row for row in baseline.get("proposals", [])}
    new_rows = {row["candidate_id"]: row for row in candidate.get("proposals", [])}
    if not old_rows or set(old_rows) != set(new_rows):
        raise ValueError("Karşılaştırılan soru kimlikleri birebir eşleşmeli")

    rows = []
    overlap_counts: list[int] = []
    unseen_counts: list[int] = []
    selection_reasons: Counter[str] = Counter()
    for candidate_id in sorted(old_rows):
        old_cards = old_rows[candidate_id].get("suggestions", [])
        new_cards = new_rows[candidate_id].get("suggestions", [])
        old_signatures = {_signature(card) for card in old_cards}
        new_signatures = {_signature(card) for card in new_cards}
        overlap = len(old_signatures & new_signatures)
        unseen = len(new_signatures - old_signatures)
        overlap_counts.append(overlap)
        unseen_counts.append(unseen)
        selection_reasons.update(
            card.get("selection_reason", "unspecified") for card in new_cards
        )
        rows.append({
            "candidate_id": candidate_id,
            "baseline_candidate_count": len(old_cards),
            "candidate_candidate_count": len(new_cards),
            "overlap_by_source_page_geometry": overlap,
            "unseen_by_source_page_geometry": unseen,
        })

    times = [
        row["retrieval_ms"]
        for row in candidate.get("proposals", [])
        if isinstance(row.get("retrieval_ms"), (int, float))
    ]
    return {
        "schema": "evidence-queue-delta-diagnostic-v1",
        "baseline_strategy": baseline.get("retrieval_strategy"),
        "candidate_strategy": candidate.get("retrieval_strategy"),
        "source_checksum": candidate.get("source_checksum"),
        "corpus_checksum": candidate.get("corpus_checksum"),
        "question_count": len(rows),
        "baseline_candidate_count": sum(row["baseline_candidate_count"] for row in rows),
        "candidate_candidate_count": sum(row["candidate_candidate_count"] for row in rows),
        "overlap_candidate_count": sum(overlap_counts),
        "unseen_candidate_count": sum(unseen_counts),
        "questions_with_unseen_candidates": sum(count > 0 for count in unseen_counts),
        "questions_without_unseen_candidates": sum(count == 0 for count in unseen_counts),
        "unseen_per_question_median": statistics.median(unseen_counts),
        "candidate_selection_reasons": dict(sorted(selection_reasons.items())),
        "candidate_retrieval_ms_p50": round(statistics.median(times), 2) if times else None,
        "candidate_retrieval_ms_p95": round(_percentile(times, 0.95), 2) if times else None,
        "interpretation": (
            "Aday çeşitliliği karşılaştırmasıdır; ilgili kanıtı bulma, doğruluk veya ürün kabulü ölçmez."
        ),
        "rows": rows,
    }


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Percentile için en az bir ölçüm gerekli")
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(
        json.loads(args.baseline.read_text(encoding="utf-8")),
        json.loads(args.candidate.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
