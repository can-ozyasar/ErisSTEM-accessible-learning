from app.pipeline.project_official_ayt_target_candidates import build


def _inputs():
    candidates = {"schema": "official-ayt-target-candidate-pool-v1", "rows": [{"candidate_id": "q1", "source_checksum": "official", "answer_key_accessed": False, "worked_explanation_accessed": False, "question": {}}]}
    audit = {"schema": "teacher-official-ayt-target-audit-v1", "answer_key_accessed": False, "worked_explanation_accessed": False,
             "reviewer_kind": "history_teacher_agent_v1", "is_human_teacher_approval": False,
             "rows": [{"candidate_id": "q1", "reviewer_kind": "history_teacher_agent_v1", "target_section_decision": {"status": "target_candidate", "sections": ["2.1"]}, "error_or_relation_type": "neden_sonuc", "required_evidence_roles": ["primary"], "coaching_suitability": {}, "quality_risks": [], "source_review_priority": "P1", "rationale": "uygun"}]}
    scope = {"schema": "ayt-target-scope-manifest-v1", "sections": [{"section_id": item} for item in ("1.3", "2.1", "2.4", "2.5", "3.1", "3.2")]}
    return candidates, audit, scope


def test_projects_only_agent_scoped_candidates_and_keeps_runtime_closed():
    result = build(*_inputs())
    assert result["candidate_count"] == 1
    assert result["rows"][0]["target_section_options"] == ["2.1"]
    assert result["is_human_teacher_approval"] is False
    assert result["runtime_enabled"] is False


def test_rejects_missing_agent_provenance():
    candidates, audit, scope = _inputs()
    audit["reviewer_kind"] = "person"
    try:
        build(candidates, audit, scope)
    except ValueError as error:
        assert "provenance" in str(error)
    else:
        raise AssertionError("agent provenance must be explicit")
