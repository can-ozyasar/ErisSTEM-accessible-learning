import pytest

from app.pipeline.assemble_ogm_ayt_pilot_readiness import build, usage_template


def _review():
    return {
        "schema": "ogm-ayt-real-question-review-v1",
        "source_name": "deneme.pdf",
        "source_checksum": "a" * 64,
        "review_count": 2,
        "reviews": [
            {"id": "q1", "checks": {"pdf_text_matches": True, "choices_complete_and_ordered": True,
                                        "text_only_accessible": True, "scope_appropriate": True}},
            {"id": "q2", "checks": {"pdf_text_matches": True, "choices_complete_and_ordered": False,
                                        "text_only_accessible": True, "scope_appropriate": True}},
        ],
    }


def _usage():
    usage = usage_template("deneme.pdf", "a" * 64)
    usage.update({"basis_kind": "documented_permission", "basis_reference": "Yerel kullanım koşulu kaydı", "confirmed_by": "İncelemeci", "confirmed_at": "2026-11-23", "local_pilot_confirmed": True})
    return usage


def test_readiness_only_accepts_all_text_transcription_checks():
    result = build(_review(), _usage())
    assert [item["id"] for item in result["approved_transcription_candidates"]] == ["q1"]
    assert [item["id"] for item in result["blocked_candidates"]] == ["q2"]
    assert result["runtime_enabled"] is False
    assert result["answer_key_accessed"] is False


def test_readiness_accepts_explicit_project_owner_review_record():
    review = _review()
    review["schema"] = "ogm-ayt-real-question-project-owner-review-v1"
    result = build(review, _usage())
    assert result["approved_transcription_candidates"][0]["id"] == "q1"


def test_readiness_rejects_unconfirmed_usage_or_checksum_mismatch():
    usage = _usage()
    usage["local_pilot_confirmed"] = False
    with pytest.raises(ValueError, match="doğrulaması eksik"):
        build(_review(), usage)
    usage = _usage()
    usage["source_checksum"] = "b" * 64
    with pytest.raises(ValueError, match="checksum"):
        build(_review(), usage)
