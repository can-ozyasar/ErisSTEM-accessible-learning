from app.pipeline.build_ayt_knowledge_graph import build


def test_graph_builder_cli_payload_keeps_review_gate():
    corpus = {
        "schema": "multi-history-rag-v1", "corpus_checksum": "0" * 32,
        "books": [{"source_name": "book.pdf", "source_checksum": "a" * 32,
                   "index": {"sections": [{"id": "1.1", "title": "Millî Mücadele"}],
                              "chunks": [{"id": "c1", "section_id": "1.1", "section_title": "Millî Mücadele",
                                          "text": "TBMM açıldı.", "quality": {"quality_checked": False},
                                          "pre_review": {"decision": "review_for_approval"}}]}}],
    }
    payload = build(corpus)
    assert payload["schema"] == "ayt-history-knowledge-graph-v1"
    assert not any(node["approved"] for node in payload["nodes"])
