import copy
import pytest

from app.pipeline.validate_ogm_ayt_target_section_audit import validate


def _audit():
    card = {"record_id": "r1", "pdf_crop_checked": True}
    return {
        "schema": "teacher-ogm-ayt-target-section-evidence-audit-v1",
        "reviewer_kind": "history_teacher_agent_v1",
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "runtime_enabled": False, "qlora_enabled": False, "is_human_teacher_approval": False,
        "records": [{"candidate_id": "q1", "decision": "direct", "pdf_crop_checked": True,
                     "supporting_record_ids": ["r1"], "card_decisions": [card], "relation_edges": []}],
        "summary": {"candidate_count": 1},
    }


def test_validates_row_local_support():
    result = validate(_audit(), expected_candidates=1)
    assert result["supported_candidate_count"] == 1


def test_rejects_missing_crop_check():
    audit = _audit(); audit["records"][0]["card_decisions"][0]["pdf_crop_checked"] = False
    with pytest.raises(ValueError):
        validate(audit)


def test_rejects_cross_row_support():
    audit = _audit(); audit["records"][0]["supporting_record_ids"] = ["other"]
    with pytest.raises(ValueError):
        validate(audit)
