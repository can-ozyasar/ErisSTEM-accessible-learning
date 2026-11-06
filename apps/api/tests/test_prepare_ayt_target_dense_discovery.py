from app.pipeline.prepare_ayt_target_dense_discovery import build


def test_dense_discovery_keeps_answers_out_and_binds_corpus():
    record = {"id": "a", "section_id": "2.1", "section_title": "Hazırlık", "page": 1, "bbox": [0, 0, 1, 1], "text": "Ankara Antlaşması", "heading": None, "pre_review": {"decision": "manual_review"}, "quality": {"warnings": []}}
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": [{"source_role": "primary_candidate", "source_checksum": "s", "source_name": "i.pdf", "index": {"evidence_atoms": [record], "context_chunks": [record]}}]}
    pool = {"schema": "official-ayt-target-discovery-pool-v1", "corpus_checksum": "c", "candidate_section_ids": ["2.1"], "answer_key_accessed": False, "worked_explanation_accessed": False, "rows": [{"candidate_id": "q", "transcription_status": "private_teacher_review_required", "target_section_options": ["2.1"], "question": {"stem": "Ankara Antlaşması nedir?", "choices": [{"text": "Sınır"}]}}]}
    result = build(pool, corpus)
    assert len(result["queries"]) == 1
    assert result["answer_key_accessed"] is False
    assert result["runtime_enabled"] is False


def test_dense_discovery_rejects_wrong_checksum():
    try:
        build({"schema": "official-ayt-target-discovery-pool-v1", "corpus_checksum": "bad"}, {"schema": "multi-history-rag-v1", "corpus_checksum": "other"})
    except ValueError as error:
        assert "Checksum" in str(error)
    else:
        raise AssertionError("checksum mismatch must fail closed")
