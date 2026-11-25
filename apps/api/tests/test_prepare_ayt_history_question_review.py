import hashlib
import json

import pymupdf
import pytest

from app.pipeline.prepare_ayt_history_question_review import build


def _checksum(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _candidate(checksum):
    questions = [{"id": f"authoring-{index:03d}", "question": "Özgün tarih sorusu metni.",
                  "choices": ["A", "B", "C", "D", "E"], "correct_label": "A", "explanation": "Kaynağa bağlı kısa açıklama.",
                  "spoken_question": "Özgün tarih sorusu metni.", "runtime_enabled": False,
                  "status": "source_crop_validation_required", "source_evidence": {"source_id": "meb-source-01", "source_checksum": checksum,
                  "page": 1, "bbox": [1, 1, 20, 20]}} for index in range(120)]
    raw = [{key: value for key, value in row.items() if key not in {"status", "runtime_enabled"}} for row in questions]
    return {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": _checksum(raw), "questions": questions}


def test_builds_private_human_review_queue_only(tmp_path):
    pdf = tmp_path / "tarih.pdf"
    with pymupdf.open() as document:
        document.new_page(width=100, height=100)
        document.save(pdf)
    checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
    output = tmp_path / "review"
    result = build(_candidate(checksum), {"schema": "ayt-history-meb-source-catalog-v1", "sources": [{"id": "meb-source-01", "source_checksum": checksum}]}, tmp_path, output)
    assert result["review_count"] == 120
    assert result["runtime_enabled"] is False
    assert result["is_human_teacher_approval"] is False
    assert all(row["status"] == "review_required" for row in result["reviews"])
    assert len(list((output / "crops").glob("*.png"))) == 120


def test_rejects_candidate_without_matching_local_source(tmp_path):
    with pytest.raises(ValueError, match="yerel ve kataloglanmış"):
        build(_candidate("a" * 64), {"schema": "ayt-history-meb-source-catalog-v1", "sources": [{"id": "meb-source-01", "source_checksum": "a" * 64}]}, tmp_path, tmp_path / "output")


def test_rejects_missing_upstream_selection_checksum(tmp_path):
    candidate = _candidate("a" * 64)
    candidate["candidate_checksum"] = "not-a-checksum"
    with pytest.raises(ValueError, match="seçim checksum"):
        build(candidate, {"schema": "ayt-history-meb-source-catalog-v1", "sources": [{"id": "meb-source-01", "source_checksum": "a" * 64}]}, tmp_path, tmp_path / "output")
