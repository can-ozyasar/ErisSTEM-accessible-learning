import pytest

from app.pipeline.ogm_ayt_evidence_semantic_gate import build


def _queue():
    return {"schema": "ogm-ayt-evidence-review-queue-v2", "source_checksum": "s", "corpus_checksum": "c",
            "proposals": [
                {"candidate_id": "a", "topic": "K", "status": "teacher_agent_source_review_required",
                 "suggestions": [{"chunk_id": "one"}, {"chunk_id": "two"}]},
                {"candidate_id": "b", "topic": "K", "status": "teacher_agent_source_review_required",
                 "suggestions": [{"chunk_id": "three"}]},
                {"candidate_id": "c", "topic": "K", "status": "reretrieve_claim_coverage", "suggestions": []},
            ]}


def test_gate_retains_only_direct_lead_for_human_review():
    audit = {"schema": "ogm-ayt-claim-coverage-agent-audit-v1", "source_checksum": "s", "reviews": [
        {"candidate_id": "a", "outcome": "plausibly_direct", "source_approval": False},
        {"candidate_id": "b", "outcome": "reretrieve", "source_approval": False},
    ]}
    content, report = build(_queue(), audit)
    assert content["proposals"][0]["candidate_id"] == "a"
    assert content["proposals"][0]["status"] == "teacher_human_source_approval_required"
    assert len(content["proposals"][0]["suggestions"]) == 1
    assert report["reretrieve_count"] == 1
    assert report["runtime_enabled"] is False


def test_gate_rejects_agent_source_approval():
    audit = {"schema": "ogm-ayt-claim-coverage-agent-audit-v1", "source_checksum": "s", "reviews": [
        {"candidate_id": "a", "outcome": "plausibly_direct", "source_approval": True},
        {"candidate_id": "b", "outcome": "reretrieve", "source_approval": False},
    ]}
    with pytest.raises(ValueError, match="Agent kanıt onayı"):
        build(_queue(), audit)
