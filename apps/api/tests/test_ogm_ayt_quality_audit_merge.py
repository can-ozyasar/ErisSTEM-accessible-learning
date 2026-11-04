import pytest

from app.pipeline.ogm_ayt_quality_audit_merge import merge


def _row(candidate_id: str, topic: str = "Konu") -> dict:
    return {"candidate_id": candidate_id, "topic": topic, "page": 1,
            "transcription_status": "clear", "source_approval": "not_granted"}


def _flags(schema: str, rows: list[dict]) -> dict:
    return {"schema": schema, "source_checksum": "x", "is_teacher_approval": False,
            "answer_key_accessed": False, "worked_explanation_accessed": False,
            "runtime_enabled": False, "qlora_enabled": False, "candidates": rows}


def test_quality_audit_merge_requires_full_unapproved_incremental_partition():
    transcriptions = {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "x", "rows": [
        {"candidate_id": "old", "topic": "Konu", "page": 1,
         "transcription_status": "private_teacher_review_required"},
        {"candidate_id": "new", "topic": "Konu", "page": 1,
         "transcription_status": "private_teacher_review_required"},
    ]}
    prior = _flags("ogm-ayt-full-transcription-quality-gate-agent-audit-v1", [_row("old")])
    batch = _flags("ogm-ayt-expanded-quality-agent-batch-v1", [_row("new")])
    report = merge(transcriptions, prior, [batch])
    assert report["summary"]["question_count"] == 2
    assert report["runtime_enabled"] is False
    batch["candidates"][0]["source_approval"] = "granted"
    with pytest.raises(ValueError, match="onayı"):
        merge(transcriptions, prior, [batch])
