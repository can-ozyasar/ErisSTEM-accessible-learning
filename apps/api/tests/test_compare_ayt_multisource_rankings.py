import json
from copy import deepcopy
from pathlib import Path

from app.pipeline.compare_ayt_multisource_rankings import compare

ROOT = Path(__file__).parents[3]


def _data():
    discovery = json.loads((ROOT / "data/private/yks-ayt-source-v1/official-ayt-full-multisource-dense-discovery-local10-12-summary-v1.json").read_text(encoding="utf-8"))
    ids = [row["id"] for row in discovery["documents"]]
    base = {
        "schema": "official-ayt-full-multisource-dense-discovery-rankings-v1",
        "corpus_checksum": discovery["corpus_checksum"],
        "source_bindings": discovery["source_bindings"], "embedding_model": "model",
        "latencies_ms": [1.0] * 10, "answer_key_accessed": False, "worked_explanation_accessed": False,
        "runtime_enabled": False, "qlora_enabled": False,
        "rankings": {q["id"]: {"qwen_dense_tr": ids[:5], "bm25": ids[5:10], "rrf": ids[10:15]} for q in discovery["queries"]},
    }
    after = deepcopy(base)
    for row in after["rankings"].values():
        row["qwen_dense_tr"] = ids[1:6]
    return discovery, base, after


def test_reports_query_overlap_and_source_counts():
    discovery, before, after = _data()
    result = compare(discovery, before, after, k=5)
    assert len(result["queries"]) == 10
    assert result["queries"][0]["overlap_at_k"]["qwen_dense_tr"] == 0.6667
    assert result["runtime_enabled"] is False


def test_compares_different_corpus_checksums_with_separate_manifest():
    discovery, before, after = _data()
    after_discovery = deepcopy(discovery)
    after_discovery["corpus_checksum"] = "corrected-corpus"
    after["corpus_checksum"] = "corrected-corpus"
    result = compare(discovery, before, after, k=5, after_discovery=after_discovery)
    assert result["after_validation"]["document_count"] == result["before_validation"]["document_count"]
