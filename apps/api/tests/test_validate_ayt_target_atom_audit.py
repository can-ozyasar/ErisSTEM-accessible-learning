import pytest

from app.pipeline.validate_ayt_target_atom_audit import build


def _inputs():
    proposals = {
        "schema": "ayt-evidence-proposals-v1", "corpus_checksum": "c",
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "runtime_enabled": False, "qlora_enabled": False,
        "proposals": [{"candidate_id": "q1", "suggestions": [{"record_id": "r1"}, {"record_id": "r2"}]},
                       {"candidate_id": "q2", "suggestions": [{"record_id": "r3"}]}],
    }
    def rec(cid, decision, support):
        cards = [{"record_id": item, "support": item in support, "pdf_crop_checked": True}
                 for item in ({"q1": ["r1", "r2"], "q2": ["r3"]}[cid])]
        return {"candidate_id": cid, "decision": decision, "reviewer_kind": "history_teacher_agent_v1",
                "is_human_teacher_approval": False, "pdf_crop_checked": True,
                "answer_key_accessed": False, "worked_explanation_accessed": False,
                "runtime_enabled": False, "qlora_enabled": False,
                "supporting_record_ids": list(support), "card_decisions": cards,
                "relation_edges": [{"source_record_ids": list(support)}] if support else []}
    audit = {"schema": "teacher-official-ayt-target-atom-audit-v2", "reviewer_kind": "history_teacher_agent_v1",
             "is_human_teacher_approval": False, "answer_key_accessed": False, "worked_explanation_accessed": False,
             "runtime_enabled": False, "qlora_enabled": False,
             "records": [rec("q1", "direct", {"r1"}), rec("q2", "insufficient", set())]}
    return proposals, audit


def test_validates_row_local_atom_audit():
    proposals, audit = _inputs()
    result = build(proposals, audit)
    assert result["candidate_count"] == 2
    assert result["checked_card_count"] == 3
    assert result["supported_candidate_count"] == 1


def test_rejects_cross_row_support():
    proposals, audit = _inputs()
    audit["records"][1]["supporting_record_ids"] = ["r1"]
    audit["records"][1]["decision"] = "direct"
    with pytest.raises(ValueError, match="Kart record_id|destek"):
        build(proposals, audit)
