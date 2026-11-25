import pytest

from app.pipeline.validate_ogm_abstained_qwen_dense_output import validate


def _fixtures():
    queries = [{"id": f"q{number}", "query": "tarih sorusu"} for number in range(2)]
    documents = [{"id": f"d{number}", "search_text": "MEB kanıtı"} for number in range(12)]
    input_data = {"schema": "ogm-ayt-discovery-calibration-v1", "source_checksum": "q", "corpus_checksum": "c",
                  "queries": queries, "documents": documents, "answer_key_accessed": False,
                  "worked_explanation_accessed": False, "runtime_enabled": False, "qlora_enabled": False}
    ranking = list(reversed([row["id"] for row in documents]))
    result = {"schema": "ogm-ayt-relation-retrieval-rankings-v1", "source_checksum": "q", "corpus_checksum": "c",
              "embedding_model": "Qwen/Qwen3-Embedding-4B", "ranking_methods": ["bm25", "qwen_dense", "rrf"],
              "top_k": 12, "gpu": "Tesla T4", "answer_key_accessed": False, "worked_explanation_accessed": False,
              "runtime_enabled": False, "qlora_enabled": False,
              "rankings": {row["id"]: {method: ranking.copy() for method in ("bm25", "qwen_dense", "rrf")} for row in queries},
              "latencies_by_method_ms": {method: [2.0, 3.0] for method in ("bm25", "qwen_dense", "rrf")}}
    return input_data, result


def test_accepts_complete_answer_free_result():
    report = validate(*_fixtures())
    assert report["valid"] is True
    assert report["query_count"] == 2


def test_rejects_checksum_or_foreign_document():
    input_data, result = _fixtures()
    result["corpus_checksum"] = "other"
    with pytest.raises(ValueError, match="checksum"):
        validate(input_data, result)
    input_data, result = _fixtures()
    result["rankings"]["q0"]["rrf"][0] = "foreign"
    with pytest.raises(ValueError, match="geçersiz rrf"):
        validate(input_data, result)
