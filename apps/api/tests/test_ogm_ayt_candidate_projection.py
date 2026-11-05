import pytest

from app.pipeline.ogm_ayt_candidate_projection import build


def _source() -> dict:
    return {
        "schema": "ogm-ayt-private-transcription-v1",
        "source_checksum": "source-v1",
        "rows": [{
            "candidate_id": "q1", "topic": "Millî Mücadele",
            "transcription_status": "private_teacher_review_required",
            "answer_key_accessed": False, "worked_explanation_accessed": False,
            "question": {"stem": "Bu alan projeksiyona geçmez."},
        }],
    }


def test_projection_is_answer_free_and_contains_only_bundle_identity_metadata():
    result = build(_source(), ["q1"])
    assert result["schema"] == "ayt-tarih2-candidates-v1"
    assert result["candidates"] == [{
        "candidate_id": "q1", "exam_year": None, "year_status": "bound", "topic": "Millî Mücadele",
    }]
    assert "question" not in result["candidates"][0]


def test_projection_rejects_answer_or_solution_access():
    source = _source()
    source["rows"][0]["answer_key_accessed"] = True
    with pytest.raises(ValueError, match="Cevap anahtarı"):
        build(source, ["q1"])
