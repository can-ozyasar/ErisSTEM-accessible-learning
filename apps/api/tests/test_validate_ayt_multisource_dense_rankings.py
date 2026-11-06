import json
from pathlib import Path

import pytest

from app.pipeline.validate_ayt_multisource_dense_rankings import build

ROOT = Path(__file__).parents[3]


def _data():
    discovery = json.loads((ROOT / "data/private/yks-ayt-source-v1/official-ayt-full-multisource-dense-discovery-local10-12-summary-v1.json").read_text(encoding="utf-8"))
    ids = [row["id"] for row in discovery["documents"]]
    rankings = {
        "schema": "official-ayt-full-multisource-dense-discovery-rankings-v1",
        "corpus_checksum": discovery["corpus_checksum"],
        "source_bindings": discovery["source_bindings"],
        "latencies_ms": {"query_p50": 1.0, "query_p95": 2.0},
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "rankings": {
            query["id"]: {"qwen_dense_tr": ids[:5], "bm25": ids[5:10], "rrf": ids[10:15]}
            for query in discovery["queries"]
        },
    }
    return discovery, rankings


def test_validates_full_answer_free_rankings():
    discovery, rankings = _data()
    result = build(discovery, rankings)
    assert result["document_count"] == 7502
    assert result["query_count"] == 10
    assert result["ranking_counts"]["rrf"] == 50


def test_rejects_unknown_document_id():
    discovery, rankings = _data()
    rankings["rankings"][next(iter(rankings["rankings"]))]["rrf"][0] = "missing"
    with pytest.raises(ValueError, match="keşif dışı"):
        build(discovery, rankings)


def test_rejects_answer_key_access():
    discovery, rankings = _data()
    rankings["answer_key_accessed"] = True
    with pytest.raises(ValueError, match="answer_key_accessed"):
        build(discovery, rankings)


def test_accepts_legacy_per_query_latency_list():
    discovery, rankings = _data()
    rankings["latencies_ms"] = [1.0] * len(discovery["queries"])
    assert build(discovery, rankings)["latencies_ms"] == rankings["latencies_ms"]
