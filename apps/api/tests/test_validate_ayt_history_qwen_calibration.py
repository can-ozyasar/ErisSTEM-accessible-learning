import pytest

from app.pipeline.validate_ayt_history_qwen_calibration import validate


def _inputs():
    queries = [{"id": f"q-{index}"} for index in range(24)]
    documents = [{"id": f"a-{index}"} for index in range(3011)]
    calibration = {"schema": "ogm-ayt-discovery-calibration-v1", "source_checksum": "a" * 64,
                   "corpus_checksum": "b" * 64, "queries": queries, "documents": documents}
    rankings = {query["id"]: {method: [f"a-{offset}" for offset in range(24)]
                              for method in ("bm25", "qwen_dense", "rrf")} for query in queries}
    ranking = {"schema": "ogm-ayt-relation-retrieval-rankings-v1", "source_checksum": "a" * 64,
               "corpus_checksum": "b" * 64, "query_count": 24, "document_count": 3011,
               "top_k": 24, "ranking_methods": ["bm25", "qwen_dense", "rrf"], "rankings": rankings,
               "latencies_by_method_ms": {method: [10.0] * 24 for method in ("bm25", "qwen_dense", "rrf")},
               "embedding_model": "Qwen/Qwen3-Embedding-4B", "gpu": "Tesla T4"}
    return calibration, ranking


def test_validates_expected_frozen_qwen_challenger():
    calibration, ranking = _inputs()
    result = validate(calibration, ranking, ranking_checksum="c" * 64)
    assert result["latency_summary_ms"]["qwen_dense"]["p95_ms"] == 10.0
    assert result["runtime_enabled"] is False


def test_rejects_extra_or_missing_method():
    calibration, ranking = _inputs()
    ranking["ranking_methods"].append("rrf_rerank")
    with pytest.raises(ValueError, match="BM25"):
        validate(calibration, ranking, ranking_checksum="c" * 64)


def test_rejects_foreign_atom_id():
    calibration, ranking = _inputs()
    ranking["rankings"]["q-0"]["rrf"][0] = "foreign"
    with pytest.raises(ValueError, match="corpus dışında"):
        validate(calibration, ranking, ranking_checksum="c" * 64)
