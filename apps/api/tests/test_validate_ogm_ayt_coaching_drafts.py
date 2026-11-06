import pytest

from app.pipeline.validate_ogm_ayt_coaching_drafts import validate, STAGES


def _payload():
    source = {"records": [{"question_id": "q1", "evidence": [{"source_id": "s1", "excerpt": "Kanıt cümlesi."}]}]}
    rows = [{"question_id": "q1", "stage": stage, "source_ids": ["s1"], "evidence_quotes": ["Kanıt cümlesi."],
             "guide_response": "Öğrenciyi düşünmeye yönlendiren kısa soru.", "early_answer_disclosed": False,
             "answer_key_or_gold_choice_included": False, "status": "ready_for_agent_review"} for stage in STAGES]
    payload = {"schema": "teacher-ogm-ayt-coaching-drafts-v1", "reviewer_kind": "history_teacher_agent_v1", "is_human_teacher_approval": False,
               "answer_key_accessed": False, "worked_explanation_accessed": False, "runtime_enabled": False, "qlora_enabled": False, "records": rows}
    return payload, source


def test_validates_complete_group():
    assert validate(*_payload(), expected_groups=1)["question_groups"] == 1


def test_rejects_early_answer_leak():
    payload, source = _payload(); payload["records"][0]["guide_response"] = "Doğru cevap A."
    with pytest.raises(ValueError): validate(payload, source, expected_groups=1)

