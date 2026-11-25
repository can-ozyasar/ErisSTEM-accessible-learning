import pytest

from app.pipeline.prepare_ayt_history_retrieval_challenger_cases import build


def _inputs():
    ids = [f"q-{index}" for index in range(24)]
    candidate = {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64,
                 "corpus_checksum": "b" * 64}
    split = {"schema": "ayt-history-candidate-split-v1",
             "records": [{"id": identifier, "split": "retrieval_test"} for identifier in ids]}
    ranking = {"schema": "ogm-ayt-relation-retrieval-rankings-v1", "source_checksum": "a" * 64,
               "corpus_checksum": "b" * 64, "ranking_methods": ["bm25", "qwen_dense", "rrf"],
               "rankings": {identifier: {method: [f"{method}-{number}" for number in range(3)]
                                           for method in ("bm25", "qwen_dense", "rrf")} for identifier in ids}}
    return candidate, split, ranking


def test_projects_dense_candidates_for_existing_blind_pdf_reviewer():
    result = build(*_inputs(), "qwen_dense")
    assert result["challenger_method"] == "qwen_dense"
    assert len(result["cases"]) == 24
    assert result["cases"][0]["retrieved_atom_ids"] == ["qwen_dense-0", "qwen_dense-1", "qwen_dense-2"]
    assert result["answer_key_accessed"] is False


def test_rejects_reranker_or_unfrozen_ranking_method():
    candidate, split, ranking = _inputs()
    with pytest.raises(ValueError, match="Yalnız BM25"):
        build(candidate, split, ranking, "rrf_rerank")
    ranking["ranking_methods"].append("rrf_rerank")
    with pytest.raises(ValueError, match="eşleşmeli"):
        build(candidate, split, ranking, "rrf")
