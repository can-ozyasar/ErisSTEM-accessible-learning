import pytest

from app.pipeline.audit_dort_dortluk_v10_combined_review import validate


def fixture_data():
    card = {
        "card_label": "E1", "chunk_id": "abc", "source_page": 4,
        "indexed_excerpt": "Kısa bir tarih kanıtı burada yer alır.",
    }
    review_input = {
        "schema": "dort-dortluk-v10-combined-support-review-input-v1",
        "review_scope": "combined_candidate_evidence_only",
        "source_checksum": "s", "corpus_checksum": "c", "question_count": 1,
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "teacher_approval": False, "runtime_enabled": False,
        "qlora_enabled": False, "kaggle_enabled": False,
        "rows": [{"candidate_id": "q1", "evidence_cards": [card]}],
    }
    report = {
        "schema": "dort-dortluk-combined-support-agent-review-v1",
        "review_scope": "research_only_combined_bundle_diagnostic",
        "source_checksum": "s", "corpus_checksum": "c",
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "teacher_approval": False, "runtime_enabled": False,
        "qlora_enabled": False, "kaggle_enabled": False,
        "summary": {"decision_counts": {"direct": 1}},
        "rows": [{
            "candidate_id": "q1", "original_question_page_checked": True,
            "all_supplied_crops_checked": True, "decision": "direct",
            "evidence_cards_checked": [{"card_label": "E1", "crop_checked": True, "cited": True}],
            "citations": [{"card_label": "E1", "chunk_id": "abc", "source_page": 4,
                           "exact_visible_quote": "kısa bir tarih kanıtı",
                           "indexed_text_ready": True}],
        }],
    }
    return review_input, report


def test_validates_complete_blind_review_and_indexed_quotes():
    result = validate(*fixture_data())
    assert result["evidence_cards_checked"] == 1
    assert result["indexed_text_ready_citations"] == 1
    assert result["teacher_approval"] is False


def test_rejects_missing_reviewed_crop():
    review_input, report = fixture_data()
    report["rows"][0]["evidence_cards_checked"] = []
    with pytest.raises(ValueError, match="coverage mismatch"):
        validate(review_input, report)


def test_rejects_quote_not_present_in_indexed_excerpt():
    review_input, report = fixture_data()
    report["rows"][0]["citations"][0]["exact_visible_quote"] = "yanlış alıntı"
    with pytest.raises(ValueError, match="absent from indexed excerpt"):
        validate(review_input, report)


def test_rejects_any_runtime_or_training_approval():
    review_input, report = fixture_data()
    report["runtime_enabled"] = True
    with pytest.raises(ValueError, match="runtime_enabled false"):
        validate(review_input, report)
