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
                 "reason": "Sorulan ilişki alıntıda açıkça yazılı.", "quote": QUOTE}]}]}
    integrity = {"schema": "ogm-ayt-source-integrity-v1", "source_checksum": "q",
                 "corpus_checksum": "c", "source_queue_schema": "ogm-ayt-evidence-review-queue-v3",
                 "cards": [{"source_key": SOURCE,
                 "crop_text_present": True, "needs_crop_review": False}]}
    return queue, audit, integrity


def test_agent_audit_is_structurally_checked_but_never_teacher_approved():
    queue, audit, integrity = _inputs()
    report = validate(queue, audit, integrity)
    assert report["questions_with_direct_lead"] == 1
    assert report["teacher_approved_count"] == 0
    assert not report["runtime_enabled"]
    audit["reviews"][0]["cards"][0]["quote"] = "Kaynakta olmayan iddia"
    with pytest.raises(ValueError, match="alıntısı"):
        validate(queue, audit, integrity)


def test_agent_cannot_claim_human_approval_or_skip_pdf_check():
    queue, audit, integrity = _inputs()
    audit["is_teacher_approval"] = True
    with pytest.raises(ValueError, match="is_teacher_approval"):
        validate(queue, audit, integrity)
    audit["is_teacher_approval"] = False
    integrity["cards"][0]["needs_crop_review"] = True
    with pytest.raises(ValueError, match="PDF kırpımı"):
        validate(queue, audit, integrity)
