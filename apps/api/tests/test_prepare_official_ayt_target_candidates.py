from app.pipeline.prepare_official_ayt_target_candidates import build


def _candidate(identifier: str, valid: bool = True):
    return {"candidate_id": identifier, "year_status": "bound", "source_checksum": "official", "test": "Tarih-1",
            "exam_year": 2025, "page": 10, "bbox": [0, 0, 1, 1],
            "question": {"parts": [{"kind": "stem", "text": "Bir tarih sorusu"}],
                         "choices": [{"label": label, "text": label if valid else ""} for label in "ABCDE"], "visuals": []}}


def test_normalizes_only_complete_bound_official_questions_without_answers():
    source = {"schema": "ayt-tarih2-candidates-v1", "candidates": [_candidate("keep"), _candidate("drop", False)]}
    result = build(source)
    assert result["candidate_count"] == 1
    assert result["rows"][0]["candidate_id"] == "keep"
    assert result["answer_key_accessed"] is False
    assert result["runtime_enabled"] is False


def test_rejects_incompatible_source_schema():
    try:
        build({"schema": "wrong", "candidates": []})
    except ValueError as error:
        assert "şeması" in str(error)
    else:
        raise AssertionError("source schema must be checked")
