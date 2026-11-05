from app.pipeline.official_ayt_scope_report import build


def test_scope_report_stays_provisional_until_both_ayt_series_are_reviewed():
    tags = {"schema": "official-ayt-2022-2026-unit-tags-v1", "source_checksum": "s", "tags": [
        {"candidate_id": "a"}, {"candidate_id": "b"}, {"candidate_id": "c"},
    ]}
    review = {"schema": "official-ayt-2022-2026-unit-tags-review-v1", "source_checksum": "s", "reviews": [
        {"candidate_id": "a", "decision": "approved_for_scope_metadata", "grade_verified": 12, "unit_verified": "12.2"},
        {"candidate_id": "b", "decision": "approved_for_scope_metadata", "grade_verified": 12, "unit_verified": "12.2"},
        {"candidate_id": "c", "decision": "review_required", "grade_verified": 11, "unit_verified": "11.3"},
    ]}
    result = build(tags, review)
    assert result["provisional_grade"] == 12
    assert result["provisional_units"] == [{"unit_id": "12.2", "question_count": 2}]
    assert result["selection_ready"] is False
