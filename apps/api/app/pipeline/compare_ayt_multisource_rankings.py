"""Compare two answer-free AYT retrieval ranking outputs without approving either."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .validate_ayt_multisource_dense_rankings import build as validate

METHODS = ("qwen_dense_tr", "bm25", "rrf")


def _top_overlap(left: list[str], right: list[str], k: int) -> float:
    a, b = set(left[:k]), set(right[:k])
    return len(a & b) / max(1, len(a | b))


def compare(discovery: dict, before: dict, after: dict, *, k: int = 20, after_discovery: dict | None = None) -> dict:
    if k < 1:
        raise ValueError("k en az bir olmalı")
    before_report = validate(discovery, before)
    after_discovery = after_discovery or discovery
    after_report = validate(after_discovery, after)
    if before.get("embedding_model") != after.get("embedding_model"):
        raise ValueError("Karşılaştırılan embedding modelleri eşleşmiyor")
    rows = []
    before_query_ids = {row["id"] for row in discovery["queries"]}
    after_query_ids = {row["id"] for row in after_discovery["queries"]}
    if before_query_ids != after_query_ids:
        raise ValueError("Karşılaştırılan discovery sorguları eşleşmiyor")
    for query_id in discovery["queries"]:
        query_id = query_id["id"]
        b_row, a_row = before["rankings"][query_id], after["rankings"][query_id]
        rows.append({
            "query_id": query_id,
            "overlap_at_k": {method: round(_top_overlap(b_row[method], a_row[method], k), 4) for method in METHODS},
            "changed_at_k": {method: len(set(b_row[method][:k]) ^ set(a_row[method][:k])) // 2 for method in METHODS},
        })

    def source_counts(rankings: dict, manifest: dict) -> dict[str, int]:
        by_id = {row["id"]: row for row in manifest["documents"]}
        return dict(Counter(
            by_id[document_id]["source_name"]
            for row in rankings["rankings"].values()
            for document_id in row["qwen_dense_tr"][:k]
        ))

    return {
        "schema": "official-ayt-multisource-ranking-comparison-v1",
        "corpus_checksum": discovery["corpus_checksum"],
        "embedding_model": before["embedding_model"],
        "top_k": k,
        "before_validation": {"document_count": before_report["document_count"], "query_count": before_report["query_count"]},
        "after_validation": {"document_count": after_report["document_count"], "query_count": after_report["query_count"]},
        "source_counts_before": source_counts(before, discovery),
        "source_counts_after": source_counts(after, after_discovery),
        "queries": rows,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Ranking overlap is a diagnostic comparison only; PDF crop review remains required.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--after-discovery", type=Path)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--k", type=int, default=20)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = compare(load(args.discovery), load(args.before), load(args.after), k=args.k,
                     after_discovery=load(args.after_discovery) if args.after_discovery else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"queries": len(result["queries"]), "k": result["top_k"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
