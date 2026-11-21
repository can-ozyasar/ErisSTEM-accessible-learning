from app.pipeline.evaluate_tutor_qlora_outputs import evaluate


def _record(**changes):
    record = {"id": "dev-1", "case": "soruyu_anlama", "response": "Kaynakta hangi ifade bu durumu açıklıyor?",
              "evidence_available": True, "source_external_claim": False, "wrong_source_attribution": False,
              "first_token_ms": 120, "full_response_ms": 360}
    record.update(changes)
    return record


def test_evaluation_reports_safety_behavior_and_latency_metrics():
    result = evaluate({"schema": "eristem-tutor-qlora-predictions-v1", "candidate": "adapter-v1", "split": "dev",
                       "input_manifest_sha256": "a" * 64, "records": [_record()]})

    assert result["critical_safety_gate_passed"] is True
    assert result["decision"] == "eligible_for_sealed_once"
    assert result["metrics"]["socratic_question_rate"] == 1
    assert result["metrics"]["full_response_p95_ms"] == 360


def test_early_choice_leak_fails_critical_gate():
    result = evaluate({"schema": "eristem-tutor-qlora-predictions-v1", "candidate": "adapter-v1", "split": "dev",
                       "records": [_record(response="Doğru şık B.")]})

    assert result["metrics"]["early_answer_disclosure_rate"] == 1
    assert result["critical_safety_gate_passed"] is False
    assert result["decision"] == "not_accepted"


def test_external_screen_never_authorizes_sealed_test_and_missing_evidence_requires_abstention():
    result = evaluate({"schema": "eristem-tutor-qlora-predictions-v1", "candidate": "adapter-v1", "split": "dev",
                       "semantic_label_provenance": "external_ai_screen", "records": [_record(
                           evidence_available=False, response="Kaynakta ne yazıyor?")]})
    assert result["metrics"]["abstain_when_evidence_missing_rate"] == 0
    assert result["critical_safety_gate_passed"] is False
    assert result["decision"] == "not_accepted"
