from app.pipeline.prepare_ayt_target_multiquery_discovery import build


def test_multiquery_uses_each_choice_as_unlabeled_retrieval_hypothesis():
    record = {"id": "e", "section_id": "2.1", "section_title": "Hazırlık", "page": 1, "bbox": [0, 0, 1, 1], "text": "Ankara", "pre_review": {"decision": "manual_review"}, "quality": {"warnings": []}}
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": [{"source_role": "primary_candidate", "source_checksum": "s", "source_name": "i", "index": {"evidence_atoms": [record], "context_chunks": [record]}}]}
    pool = {"schema": "official-ayt-target-discovery-pool-v1", "corpus_checksum": "c", "candidate_section_ids": ["2.1"], "answer_key_accessed": False, "worked_explanation_accessed": False, "rows": [{"candidate_id": "q", "target_section_options": ["2.1"], "question": {"stem": "Soru kökü", "choices": [{"label": "A", "text": "ilk varsayım"}, {"label": "B", "text": "ikinci varsayım"}]}}]}
    result = build(pool, corpus)
    subqueries = result["queries"][0]["subqueries"]
    assert [item["kind"] for item in subqueries] == ["question_root", "choice_hypothesis", "choice_hypothesis"]
    assert "label" not in subqueries[0]
    assert result["answer_key_accessed"] is False
