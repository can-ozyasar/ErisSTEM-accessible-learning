import pytest

from app.pipeline.ogm_ayt_crop_repair_merge import build


def _source():
    return {"layout": {"column": 0}}


def _row(candidate_id: str):
    return {"candidate_id": candidate_id, "topic": "Konu", "page": 1, "source": _source(),
            "transcription_status": "private_teacher_review_required"}


def _repair(candidate_id: str):
    return {"candidate_id": candidate_id, "topic": "Konu", "page": 1, "repair_status": "repaired_clear",
            "question": {"stem": "Bu yeterli bir soru köküdür.", "choices": [
                {"label": label, "text": f"Seçenek {label}"} for label in "ABCDE"]}, "source": _source(),
            "pdf_crop_checked": True, "repair_notes": "PDF kesitiyle tek tek doğrulandı.",
            "source_approval": "not_granted", "runtime_eligible": False, "qlora_eligible": False}


def test_crop_repair_merge_requires_pdf_checked_unapproved_repair():
    clear = {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "x", "rows": [_row("clear")]}
    original = {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "x", "rows": [_row("clear"), _row("repair")]}
    audit = {"source_checksum": "x", "candidates": [{"candidate_id": "clear", "transcription_status": "clear"},
             {"candidate_id": "repair", "transcription_status": "recoverable_with_crop"}]}
    flags = {"schema": "ogm-ayt-crop-repair-agent-batch-v1", "source_checksum": "x", "is_teacher_approval": False,
             "answer_key_accessed": False, "worked_explanation_accessed": False, "runtime_enabled": False, "qlora_enabled": False}
    content, report = build(clear, audit, original, [{**flags, "repairs": [_repair("repair")]}, {**flags, "repairs": []}], target=2)
    assert len(content["rows"]) == 2
    assert report["source_approved_count"] == 0
    broken = _repair("repair")
    broken["pdf_crop_checked"] = False
    with pytest.raises(ValueError, match="PDF kırpımı"):
        build(clear, audit, original, [{**flags, "repairs": [broken]}, {**flags, "repairs": []}], target=2)
