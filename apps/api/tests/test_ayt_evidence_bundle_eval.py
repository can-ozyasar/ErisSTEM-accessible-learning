import pytest

from app.pipeline.ayt_evidence_bundle_eval import compare, summarize


def _proposals(status="reretrieve_required", missing=None, review_status="discovery_candidate"):
    missing = ["c2"] if missing is None else missing
    return {"schema": "ayt-evidence-bundle-proposals-v1", "corpus_checksum": "c", "question_source_checksum": "q",
            "proposals": [{"status": status, "evidence_plan": {"required_claim_ids": ["c1", "c2"], "missing_claim_ids": missing},
                           "suggestions": [{"review_status": review_status}]}]}


def test_bundle_summary_separates_discovery_from_approval():
    result = summarize(_proposals())
    assert result["summary"]["required_claim_coverage"] == 0.5
    assert result["summary"]["source_approval_count"] == 0


def test_bundle_comparison_reports_coverage_delta_and_checks_version():
    result = compare(_proposals(), _proposals("teacher_review_required", []))
    assert result["delta"]["missing_claims"] == -1
    assert result["delta"]["strict_complete_candidate_count"] == 1
    changed = _proposals()
    changed["corpus_checksum"] = "other"
    with pytest.raises(ValueError, match="aynı kaynak sürümüne"):
        compare(_proposals(), changed)
