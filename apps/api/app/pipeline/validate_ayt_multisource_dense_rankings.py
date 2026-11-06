"""Validate answer-free AYT dense retrieval rankings against their discovery input."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DISCOVERY_SCHEMAS = {
    "ayt-multisource-dense-discovery-v1",
    "ayt-full-multisource-dense-discovery-v1",
}
RANKING_SCHEMAS = {
    "official-ayt-multisource-dense-discovery-rankings-v1",
    "official-ayt-full-multisource-dense-discovery-rankings-v1",
}
METHODS = ("qwen_dense_tr", "bm25", "rrf")
SAFETY_FLAGS = ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled")


def _assert_false(payload: dict) -> None:
    for key in SAFETY_FLAGS:
        if payload.get(key) is not False:
            raise ValueError(f"{key} false olmalı")


def build(discovery: dict, rankings: dict) -> dict:
    if discovery.get("schema") not in DISCOVERY_SCHEMAS:
        raise ValueError("Tanımlı AYT keşif şeması gerekli")
    if rankings.get("schema") not in RANKING_SCHEMAS:
        raise ValueError("Tanımlı AYT sıralama şeması gerekli")
    _assert_false(discovery)
    _assert_false(rankings)
    if rankings.get("corpus_checksum") != discovery.get("corpus_checksum"):
        raise ValueError("Sıralama corpus checksum değeriyle eşleşmiyor")
    if rankings.get("source_bindings") != discovery.get("source_bindings"):
        raise ValueError("Sıralama kaynak bağlarıyla eşleşmiyor")

    document_ids = {row.get("id") for row in discovery.get("documents", [])}
    if not document_ids or None in document_ids:
        raise ValueError("Keşif belgelerinde benzersiz id gerekli")
    query_ids = {row.get("id") for row in discovery.get("queries", [])}
    ranking_rows = rankings.get("rankings")
    if not isinstance(ranking_rows, dict) or set(ranking_rows) != query_ids:
        raise ValueError("Sıralama sorgu kimlikleri keşifle tam eşleşmeli")

    counts: dict[str, int] = {method: 0 for method in METHODS}
    max_depth = 0
    for query_id, row in ranking_rows.items():
        if not isinstance(row, dict):
            raise ValueError(f"{query_id} sıralaması nesne olmalı")
        for method in METHODS:
            values = row.get(method)
            if not isinstance(values, list) or not values:
                raise ValueError(f"{query_id} için {method} sıralaması boş")
            if len(values) != len(set(values)):
                raise ValueError(f"{query_id} {method} sıralamasında tekrar var")
            if any(value not in document_ids for value in values):
                raise ValueError(f"{query_id} {method} keşif dışı belge içeriyor")
            counts[method] += len(values)
            max_depth = max(max_depth, len(values))

    latencies = rankings.get("latencies_ms", {})
    # Earlier runner versions wrote one latency per query as a list; newer
    # runners may expose p50/p95 fields. Preserve either explicit format while
    # rejecting arbitrary values.
    if not isinstance(latencies, (dict, list)):
        raise ValueError("latencies_ms nesne veya liste olmalı")
    return {
        "schema": "official-ayt-multisource-dense-rankings-validation-v1",
        "ranking_schema": rankings["schema"],
        "corpus_checksum": discovery["corpus_checksum"],
        "source_bindings": discovery["source_bindings"],
        "document_count": len(document_ids),
        "query_count": len(query_ids),
        "ranking_counts": counts,
        "max_ranking_depth": max_depth,
        "latencies_ms": latencies,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Schema, provenance and safety validation only; rankings remain PDF-crop review leads.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.discovery), load(args.rankings))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"documents": result["document_count"], "queries": result["query_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
