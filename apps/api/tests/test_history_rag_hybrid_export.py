from app.history_rag_hybrid import approval_checksum


def test_export_checksum_covers_the_full_approved_corpus_not_only_query_hits():
    source = "pdf-v1"
    all_approved = {"a", "b", "c"}
    selected_for_queries = {"a"}
    assert approval_checksum(source, all_approved) != approval_checksum(source, selected_for_queries)
