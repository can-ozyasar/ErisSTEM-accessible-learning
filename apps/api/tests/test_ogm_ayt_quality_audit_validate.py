import pytest

from app.pipeline.ogm_ayt_quality_audit_validate import validate


def test_sample_counts_are_recomputed_from_source_bound_cards():
    queue = {"schema": "ogm-ayt-evidence-review-queue-v3", "source_checksum": "q",
             "corpus_checksum": "c", "proposals": [{"candidate_id": "one", "suggestions": [
                 {"source_checksum": "s", "chunk_id": "a"}]}]}
    audit = {"schema": "ogm-ayt-agent-quality-audit-v2", "source_checksum": "q",
             "corpus_checksum": "c", "is_teacher_approval": False,
             "answer_key_accessed": False, "worked_explanation_accessed": False,
             "runtime_enabled": False, "qlora_enabled": False,
             "manual_stratified_sample": [{"candidate_id": "one", "manual_finding": "İlişki mevcut.",
                 "source_approval": False, "corrected_question_outcome": "crop_review_required_before_use",
                 "cards": [{"rank": 1, "source_checksum": "s", "chunk_id": "a",
                            "verdict": "direct"}]}],
             "sample_summary": {"questions": 1, "cards": 1, "direct": 1,
                                "corrected_outcomes": {"crop_review_required_before_use": 1}}}
    report = validate(queue, audit)
    assert report["verdict_counts"]["direct"] == 1
    assert report["teacher_approved_count"] == 0
    audit["sample_summary"]["direct"] = 2
    with pytest.raises(ValueError, match="tutarsız"):
        validate(queue, audit)
