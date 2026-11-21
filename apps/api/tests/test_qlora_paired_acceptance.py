from app.pipeline.qlora_paired_acceptance import evaluate


def metric(value):
    return {"value": value}


def report(adapter_abstain=0.0):
    return {
        "status": "completed",
        "paired": {
            "base": {"metrics": {
                "early_disclosure_rate": metric(0.125),
                "ends_with_question_rate": metric(0.455),
                "abstain_when_no_evidence_rate": metric(0.0),
            }},
            "adapter": {"metrics": {
                "early_disclosure_rate": metric(0.0),
                "ends_with_question_rate": metric(1.0),
                "abstain_when_no_evidence_rate": metric(adapter_abstain),
            }},
        },
    }


def test_rejects_adapter_that_does_not_abstain():
    result = evaluate(report())
    assert result["synthetic_safety_passed"] is False
    assert result["raw_adapter_eligible_for_live_generation"] is False
    assert result["decision"] == "blocked: raw adapter did not demonstrate safe abstention"
    assert result["deltas"]["early_direct_disclosure_rate"] == -0.125


def test_successful_synthetic_safety_still_needs_sealed_evaluation():
    result = evaluate(report(adapter_abstain=1.0))
    assert result["synthetic_safety_passed"] is True
    assert result["raw_adapter_eligible_for_live_generation"] is False
    assert result["decision"] == "still_blocked_pending_sealed_and_expert_evaluation"
