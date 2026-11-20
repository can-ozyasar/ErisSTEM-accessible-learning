import pytest

from app.pipeline.assemble_authoring_source_reviews import build


def queue():
    return {"schema": "ayt-history-original-authoring-queue-v1", "corpus_checksum": "c", "queue_checksum": "q" * 64, "cards": [
        {"id": "a"}, {"id": "b"},
    ]}


def batch(rows):
    return {"schema": "deepseek-original-authoring-source-review-v1", "corpus_checksum": "c", "queue_checksum": "q" * 64, "reviews": rows}


def test_accepts_only_direct_text_only_cards_after_complete_review():
    result = build(queue(), [batch([
        {"id": "a", "verdict": "direct_fact", "text_only_candidate": True},
        {"id": "b", "verdict": "context_only", "text_only_candidate": False},
    ])])
    assert result["summary"] == {"reviewed": 2, "accepted_for_pdf_crop_review": 1, "held_out": 1}
    assert result["accepted_for_pdf_crop_review"][0]["question_authoring_enabled"] is False


def test_rejects_incomplete_review_coverage():
    with pytest.raises(ValueError, match="tam bir AI incelemesi"):
        build(queue(), [batch([{"id": "a", "verdict": "direct_fact", "text_only_candidate": True}])])


def test_rejects_review_from_a_different_authoring_queue():
    stale = batch([
        {"id": "a", "verdict": "direct_fact", "text_only_candidate": True},
        {"id": "b", "verdict": "context_only", "text_only_candidate": False},
    ])
    stale["queue_checksum"] = "x" * 64
    with pytest.raises(ValueError, match="kuyruk checksum"):
        build(queue(), [stale])
