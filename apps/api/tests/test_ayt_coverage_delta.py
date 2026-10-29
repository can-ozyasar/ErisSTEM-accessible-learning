import pytest

from app.pipeline.ayt_coverage_delta import build


def _proposal(chunk_id: str, grade: int) -> dict:
    return {
        "chunk_id": chunk_id,
        "source_checksum": f"book-{grade}",
        "grade": grade,
        "page": 10,
    }


def _manifest(corpus_checksum: str, suggestions: list[dict]) -> dict:
    return {
        "schema": "ayt-evidence-proposals-v1",
        "question_source_checksum": "questions-v1",
        "corpus_checksum": corpus_checksum,
        "proposals": [
            {"candidate_id": "bound", "exam_year": 2024,
             "status": "teacher_review_required", "suggestions": suggestions},
            {"candidate_id": "old", "exam_year": 2021,
             "status": "out_of_scope", "suggestions": []},
        ],
    }


def test_coverage_delta_is_metadata_only_and_keeps_review_gate():
    result = build(
        _manifest("base", [_proposal("old-top", 11)]),
        _manifest("coverage", [_proposal("new-top", 9), _proposal("old-top", 11)]),
    )
    assert result["bound_question_count"] == 1
    assert result["top1_changed_count"] == 1
    assert result["grade9_top3_count"] == 1
    assert result["rows"] == [{
        "candidate_id": "bound", "exam_year": 2024, "top1_changed": True,
        "baseline_top1": {"chunk_id": "old-top", "source_checksum": "book-11", "grade": 11, "page": 10},
        "coverage_top1": {"chunk_id": "new-top", "source_checksum": "book-9", "grade": 9, "page": 10},
        "grade9_candidate_ranks": [1], "grade9_in_top3": True,
    }]
    assert "may not be used" in result["notice"]


def test_coverage_delta_rejects_different_question_sources():
    baseline = _manifest("base", [])
    coverage = _manifest("coverage", [])
    coverage["question_source_checksum"] = "other"
    with pytest.raises(ValueError, match="Farklı soru kaynakları"):
        build(baseline, coverage)
