from app.pipeline.ayt_target_scope import EA_2018_2026_TARGETS, build


def _corpus():
    sections = [
        {"id": section_id, "title": title, "start": 1, "end": 2}
        for section_id, title, _count in EA_2018_2026_TARGETS
    ]
    chunks = [{"section_id": section_id} for section_id, _title, _count in EA_2018_2026_TARGETS]
    return {
        "schema": "multi-history-rag-v1",
        "corpus_checksum": "corpus",
        "books": [
            {
                "grade": 12,
                "source_name": "inkilap-12-aday-eba.pdf",
                "source_checksum": "source",
                "index_checksum": "index",
                "index": {"sections": sections, "chunks": chunks},
            }
        ],
    }


def _scope(grade=12):
    return {
        "schema": "yks-history-scope-report-v1",
        "chosen_grade": grade,
        "approved_tag_count": 26,
        "unit_ranking": [{"unit_id": "12.2", "question_count": 6}],
    }


def test_target_scope_binds_six_sections_to_reviewed_grade_and_book():
    result = build(_scope(), _corpus(), "a" * 64)
    assert result["grade"] == 12
    assert [row["section_id"] for row in result["sections"]] == [
        item[0] for item in EA_2018_2026_TARGETS
    ]
    assert result["gates"]["qlora_enabled"] is False
    assert result["gates"]["answer_key_accessed"] is False


def test_target_scope_rejects_unreviewed_grade_decision():
    try:
        build(_scope(11), _corpus(), "a" * 64)
    except ValueError as error:
        assert "12. sınıf" in str(error)
    else:
        raise AssertionError("grade mismatch must fail closed")
