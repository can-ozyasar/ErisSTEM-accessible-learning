from app.pipeline.ogm_ayt_semantic_gate import build


def test_semantic_gate_keeps_only_clear_rows():
    transcriptions = {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "s", "rows": [
        {"candidate_id": "a", "topic": "K", "page": 1, "transcription_status": "private_teacher_review_required"},
        {"candidate_id": "b", "topic": "K", "page": 2, "transcription_status": "private_teacher_review_required"},
    ]}
    audit = {"schema": "ogm-ayt-full-transcription-quality-gate-agent-audit-v1", "source_checksum": "s", "decisions": [
        {"candidate_id": "a", "transcription_quality": "clear"},
        {"candidate_id": "b", "transcription_quality": "recoverable_with_crop"},
    ]}
    content, report = build(transcriptions, audit)
    assert [row["candidate_id"] for row in content["rows"]] == ["a"]
    assert report["repair_count"] == 1
    assert report["qlora_enabled"] is False
