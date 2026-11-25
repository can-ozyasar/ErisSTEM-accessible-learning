import pytest

from app.pipeline.prepare_ogm_real_question_evidence_queue import build


def _question_pack():
    return {"schema": "ayt-target-question-candidates-v1", "source_checksum": "q", "rows": [{
        "candidate_id": "q1", "deneme_number": 1,
        "question": {"number": 25, "parts": [{"text": "Lozan Antlaşması"}],
                     "choices": [{"text": "A"}, {"text": "B"}]},
    }]}


def _readiness():
    return {"schema": "ogm-ayt-real-question-pilot-readiness-v1", "source_checksum": "q",
            "approved_transcription_candidates": [{"id": "q1"}]}


def _corpus():
    record = {"id": "a1", "section_id": "s1", "section_title": "Lozan", "page": 2,
              "bbox": [1, 2, 3, 4], "text": "Lozan Antlaşması", "heading": "Barış",
              "quality": {"warnings": []}, "pre_review": {"decision": "manual_review"}}
    return {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": [{
        "source_name": "meb.pdf", "source_checksum": "m", "grade": 12,
        "index": {"evidence_atoms": [record], "context_chunks": [record]},
    }]}


def test_queue_is_answer_free_and_uses_only_primary_meb_candidates():
    result = build(_question_pack(), _readiness(), _corpus(), first_stage_limit=2, candidate_limit=1)
    assert result["retrieval"]["answer_key_used"] is False
    assert result["question_count"] == 1
    assert result["proposals"][0]["suggestions"][0]["source_name"] == "meb.pdf"


def test_queue_refuses_checksum_mismatch():
    readiness = _readiness()
    readiness["source_checksum"] = "other"
    with pytest.raises(ValueError, match="checksum"):
        build(_question_pack(), readiness, _corpus())
