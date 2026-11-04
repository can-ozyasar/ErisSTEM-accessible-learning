import pytest

from app.pipeline.ogm_ayt_agent_gold_merge import merge


def _queue():
    return {"schema": "ogm-ayt-evidence-review-queue-v3", "source_checksum": "q", "corpus_checksum": "c",
            "proposals": [{"candidate_id": "one", "suggestions": [{"source_checksum": "s", "chunk_id": "a"}]}]}


def _batch(verdict="support"):
    return {"source_checksum": "q", "corpus_checksum": "c", "is_teacher_approval": False,
            "answer_key_accessed": False, "worked_explanation_accessed": False,
            "runtime_enabled": False, "qlora_enabled": False, "reviews": [{"candidate_id": "one",
            "reviewed": True, "crop_checked": True, "coverage_complete": True, "reviewer": "agent",
            "reviewer_kind": "history_teacher_agent_v1", "abstain": verdict != "support",
            "judgments": [{"source_key": "s:a", "verdict": verdict}]}]}


def test_agent_gold_merge_accepts_complete_agent_review_and_rejects_missing_source():
    result = merge(_queue(), [_batch()])
    assert result["cases"][0]["reviewer_kind"] == "history_teacher_agent_v1"
    broken = _batch()
    broken["reviews"][0]["judgments"] = []
    with pytest.raises(ValueError, match="eksiksiz"):
        merge(_queue(), [broken])
