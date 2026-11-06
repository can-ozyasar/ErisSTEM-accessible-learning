from app.pipeline.prepare_ayt_target_dense_audit import build


def _record(record_id: str, kind: str):
    return {"id": record_id, "section_id": "2.1", "section_title": "Hazırlık", "page": 1,
            "bbox": [0, 0, 1, 1], "text": "Ankara Antlaşması ile sınır belirlendi.", "heading": None,
            "pre_review": {"decision": "manual_review"}, "quality": {"warnings": []},
            "extraction_method": kind}


def _inputs():
    pool = {"schema": "ayt-target-discovery-pool-v1", "corpus_checksum": "c", "candidate_section_ids": ["1.3", "2.1", "2.4", "2.5", "3.1", "3.2"], "rows": []}
    review_rows = []
    for index in range(8):
        candidate_id = f"q{index}"
        pool["rows"].append({"candidate_id": candidate_id, "topic": "Millî Mücadele", "answer_key_accessed": False,
                             "worked_explanation_accessed": False, "question": {"stem": "Ankara Antlaşması neyi belirledi?", "choices": []}})
        review_rows.append({"candidate_id": candidate_id, "assessment": "direct", "evaluation_only": True,
                            "gold_supporting_record_ids": ["atom"], "gold_label_origin": "teacher_pdf_crop_review"})
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": [{"source_role": "primary_candidate", "source_checksum": "s", "source_name": "inkilap.pdf", "index": {"evidence_atoms": [_record("atom", "standalone_fact")], "context_chunks": [_record("context", "context")]}}]}
    review = {"schema": "teacher-target-atom-context-audit-local12-v1", "source_binding": {"source_checksum": "s"},
              "answer_key_accessed": False, "worked_explanation_accessed": False, "records": review_rows}
    return pool, corpus, review


def test_dense_audit_is_answer_free_and_binds_gold_evidence_to_private_crop_review():
    pool, corpus, review = _inputs()
    result = build(pool, corpus, review)
    assert len(result["queries"]) == 8
    assert result["queries"][0]["gold_record_ids"] == ["atom"]
    assert result["runtime_enabled"] is False
    assert result["qlora_enabled"] is False


def test_dense_audit_rejects_missing_coordinate_label():
    pool, corpus, review = _inputs()
    review["records"][0]["gold_supporting_record_ids"] = []
    try:
        build(pool, corpus, review)
    except ValueError as error:
        assert "altın kanıt" in str(error)
    else:
        raise AssertionError("missing crop label must fail closed")
