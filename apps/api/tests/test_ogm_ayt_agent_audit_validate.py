import pytest

from app.pipeline.ogm_ayt_agent_audit_validate import validate

SOURCE = "s:one"
QUOTE = "Lozan Antlaşması ile bağımsızlık tanındı."


def _inputs():
    queue = {"schema": "ogm-ayt-evidence-review-queue-v3", "source_checksum": "q",
             "corpus_checksum": "c", "proposals": [{"candidate_id": "question-1", "suggestions": [
                 {"source_checksum": "s", "chunk_id": "one", "text": QUOTE}]}]}
    audit = {"schema": "ogm-ayt-full-agent-audit-v1", "source_checksum": "q",
             "corpus_checksum": "c", "is_teacher_approval": False,
             "answer_key_accessed": False, "worked_explanation_accessed": False,
             "runtime_enabled": False, "qlora_enabled": False,
             "reviews": [{"candidate_id": "question-1", "cards": [{
                 "source_checksum": "s", "chunk_id": "one", "verdict": "direct",
                 "reason": "Sorulan ilişki alıntıda açıkça yazılı.", "quote": QUOTE}],
                 "bundle_assessment": {"decision": "direct", "supporting_chunk_ids": ["one"],
                                       "reason": "Kaynak sorulan ilişkiyi doğrudan gösteriyor."}}]}
    integrity = {"schema": "ogm-ayt-source-integrity-v1", "source_checksum": "q",
                 "corpus_checksum": "c", "source_queue_schema": "ogm-ayt-evidence-review-queue-v3",
                 "cards": [{"source_key": SOURCE,
                 "crop_text_present": True, "needs_crop_review": False}]}
    return queue, audit, integrity


def test_agent_audit_is_structurally_checked_but_never_teacher_approved():
    queue, audit, integrity = _inputs()
    report = validate(queue, audit, integrity)
    assert report["questions_with_direct_lead"] == 1
    assert report["questions_with_supported_bundle"] == 1
    assert report["teacher_approved_count"] == 0
    assert not report["runtime_enabled"]
    audit["reviews"][0]["cards"][0]["quote"] = "Kaynakta olmayan iddia"
    with pytest.raises(ValueError, match="alıntısı"):
        validate(queue, audit, integrity)


def test_bundle_decision_flags_classification_inconsistency_and_rejects_foreign_ids():
    queue, audit, integrity = _inputs()
    audit["reviews"][0]["bundle_assessment"]["supporting_chunk_ids"] = ["foreign"]
    with pytest.raises(ValueError, match="adaylarıyla eşleşmeli"):
        validate(queue, audit, integrity)
    audit["reviews"][0]["bundle_assessment"]["supporting_chunk_ids"] = ["one"]
    audit["reviews"][0]["cards"][0]["verdict"] = "irrelevant"
    report = validate(queue, audit, integrity)
    assert not report["bundle_consistency_passed"]
    assert report["bundle_consistency_flags"][0]["candidate_id"] == "question-1"


def test_agent_cannot_claim_human_approval_or_skip_pdf_check():
    queue, audit, integrity = _inputs()
    audit["is_teacher_approval"] = True
    with pytest.raises(ValueError, match="is_teacher_approval"):
        validate(queue, audit, integrity)
    audit["is_teacher_approval"] = False
    integrity["cards"][0]["needs_crop_review"] = True
    with pytest.raises(ValueError, match="görsel PDF kontrolü"):
        validate(queue, audit, integrity)
    audit["reviews"][0]["cards"][0]["crop_visual_checked"] = True
    audit["reviews"][0]["cards"][0]["crop_visual_note"] = "PDF görselindeki metin kesitle örtüşüyor."
    report = validate(queue, audit, integrity)
    assert report["teacher_approved_count"] == 0


def test_quote_validation_normalizes_turkish_apostrophe_variants():
    queue, audit, integrity = _inputs()
    queue["proposals"][0]["suggestions"][0]["text"] = "Lozan Antlaşması’nda bağımsızlık tanındı."
    audit["reviews"][0]["cards"][0]["quote"] = "Lozan Antlaşması'nda bağımsızlık tanındı."
    report = validate(queue, audit, integrity)
    assert report["questions_with_direct_lead"] == 1


def test_claimwise_combined_audit_schema_is_validated_with_same_source_gates():
    queue, audit, integrity = _inputs()
    audit["schema"] = "ogm-ayt-claimwise-combined-audit-v1"
    audit["reviewers"] = ["agent-a", "agent-b"]
    report = validate(queue, audit, integrity)
    assert report["question_count"] == 1
    assert report["card_count"] == 1
    assert report["teacher_approved_count"] == 0
