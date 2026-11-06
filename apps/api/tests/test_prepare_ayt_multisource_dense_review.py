import json
from pathlib import Path

import pytest

from app.pipeline.prepare_ayt_multisource_dense_review import build

ROOT = Path(__file__).parents[3]


def _discovery() -> dict:
    return json.loads(
        (ROOT / "data/private/yks-ayt-source-v1/official-ayt-multisource-dense-discovery-local11-12-v1.json").read_text(encoding="utf-8")
    )


def _rankings(discovery: dict) -> dict:
    ids = [row["id"] for row in discovery["documents"]]
    return {
        "schema": "official-ayt-multisource-dense-discovery-rankings-v1",
        "corpus_checksum": discovery["corpus_checksum"],
        "source_bindings": discovery["source_bindings"],
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "rankings": {
            query["id"]: {"qwen_dense_tr": ids[:20], "bm25": ids[1:21], "rrf": ids[2:22]}
            for query in discovery["queries"]
        },
    }


def test_builds_checksum_bound_private_multisource_review_queue():
    discovery = _discovery()
    result = build(discovery, _rankings(discovery))
    assert result["schema"] == "official-ayt-multisource-dense-review-queue-v1"
    assert len(result["rows"]) == 10
    assert {source["grade"] for source in result["source_bindings"]} == {11, 12}
    assert all(3 <= len(row["suggestions"]) <= 10 for row in result["rows"])
    assert result["runtime_enabled"] is False


def test_rejects_different_source_bindings():
    discovery = _discovery()
    rankings = _rankings(discovery)
    rankings["source_bindings"] = []
    with pytest.raises(ValueError, match="kaynak bağları"):
        build(discovery, rankings)
