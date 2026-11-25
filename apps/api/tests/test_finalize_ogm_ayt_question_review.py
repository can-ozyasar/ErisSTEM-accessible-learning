import pytest

from app.pipeline.finalize_ogm_ayt_question_review import finalize


def _pack():
    return {
        "schema": "ogm-ayt-real-question-review-v1",
        "review_count": 1,
        "reviews": [{"id": "q1", "checks": {}, "notes": "old", "status": "review_required"}],
    }


def test_finalize_records_project_owner_review_without_opening_runtime():
    result = finalize(_pack(), "Proje sahibi")
    assert result["schema"] == "ogm-ayt-real-question-project-owner-review-v1"
    assert result["reviews"][0]["checks"] == {
        "pdf_text_matches": True,
        "choices_complete_and_ordered": True,
        "text_only_accessible": True,
        "scope_appropriate": True,
    }
    assert result["is_human_teacher_approval"] is False
    assert result["runtime_enabled"] is False


def test_finalize_refuses_empty_or_mismatched_pack():
    with pytest.raises(ValueError, match="kişi"):
        finalize(_pack(), " ")
    with pytest.raises(ValueError, match="şeması"):
        finalize({**_pack(), "schema": "wrong"}, "Proje sahibi")
