from app.pipeline.evaluate_ayt_retrieval_delta import build


def _audit(verdicts):
    return {"reviewer_kind": "history_teacher_agent_v1", "answer_key_accessed": False, "worked_explanation_accessed": False,
            "records": [{"candidate_id": key, "assessment": value, "failure_diagnosis": "none", "reviewer_kind": "history_teacher_agent_v1"} for key, value in verdicts.items()]}


def test_accepts_only_strictly_improved_agent_crop_audit_without_regression():
    result = build(_audit({"a": "wrong", "b": "direct"}), _audit({"a": "direct", "b": "direct"}))
    assert result["delta"]["support_count"] == 1
    assert result["accepted_for_next_review_stage"] is True


def test_rejects_candidate_that_loses_prior_supported_evidence():
    result = build(_audit({"a": "direct"}), _audit({"a": "wrong"}))
    assert result["accepted_for_next_review_stage"] is False
