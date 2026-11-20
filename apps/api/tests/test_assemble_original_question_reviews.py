import pytest

from app.pipeline.assemble_original_question_reviews import build


def draft(identifier: str):
    return {"schema": "deepseek-original-question-drafts-v1", "corpus_checksum": "c", "queue_checksum": "q",
            "drafts": [{"id": identifier, "runtime_enabled": False}]}


def review(identifier: str, verdict: str = "accept_for_source_validation"):
    return {"schema": "deepseek-original-question-review-v1", "corpus_checksum": "c", "queue_checksum": "q",
            "reviews": [{"id": identifier, "verdict": verdict}]}


def test_keeps_rejected_drafts_out_of_source_crop_validation_queue():
    result = build([draft("a"), draft("b")], [review("a"), review("b", "reject")])
    assert result["summary"] == {"reviewed": 2, "accepted_for_source_crop_validation": 1, "held_out": 1}
    assert result["accepted_for_source_crop_validation"][0]["runtime_enabled"] is False


def test_rejects_missing_independent_review():
    with pytest.raises(ValueError, match="tam bir bağımsız inceleme"):
        build([draft("a")], [])
