import pytest

from app.pipeline.ogm_ayt_relation_review_queue import build


def _calibration():
    return {"schema": "ogm-ayt-discovery-calibration-v1", "source_checksum": "q", "corpus_checksum": "c",
            "queries": [{"id": "question", "topic": "Konu"}], "documents": [
                {"id": f"book:{key}", "source_checksum": "book", "chunk_id": key, "grade": 12,
                 "page": 1, "bbox": [], "section_title": "Başlık", "search_text": "Metin",
                 "review_route": "priority"} for key in "abcdefghijkl"
            ]}


def _rankings():
    values = [f"book:{key}" for key in "abcdefghijkl"]
    return {"schema": "ogm-ayt-relation-retrieval-rankings-v1", "source_checksum": "q", "corpus_checksum": "c",
            "rankings": {"question": {"bm25": values, "bge_dense": values[::-1],
                                        "bge_sparse": values[2:] + values[:2], "rrf": values[1:] + values[:1],
                                        "bge_dense_rerank": values[3:] + values[:3]}}}


def _corpus():
    return {"schema": "multi-history-rag-v1", "corpus_checksum": "c",
            "books": [{"source_checksum": "book", "source_name": "kitap.pdf"}]}


def test_relation_queue_balances_methods_and_preserves_source_coordinates():
    result = build(_calibration(), _rankings(), _corpus(), limit=10)
    cards = result["proposals"][0]["suggestions"]
    assert len(cards) == 10
    assert cards[0]["source_name"] == "kitap.pdf"
    assert any("bge_dense" in card["method_ranks"] for card in cards)
    assert any("bge_dense_rerank" in card["method_ranks"] for card in cards)


def test_relation_queue_rejects_out_of_corpus_result():
    rankings = _rankings()
    rankings["rankings"]["question"]["rrf"][0] = "unknown:source"
    with pytest.raises(ValueError, match="dışında"):
        build(_calibration(), rankings, _corpus(), limit=10)
