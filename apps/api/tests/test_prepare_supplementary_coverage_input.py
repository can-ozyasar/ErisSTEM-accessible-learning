import pytest

from app.pipeline.prepare_supplementary_coverage_input import build


def _inputs():
    corpus = {
        "schema": "multi-history-rag-v1",
        "corpus_checksum": "corpus-v1",
        "books": [{
            "source_role": "supplementary_candidate", "source_checksum": "book-v1", "grade": 12,
            "student_runtime_eligible": False, "qlora_eligible": False,
            "index": {"chunks": [{"id": "chunk-1", "page": 7, "bbox": [1, 2, 3, 4],
                                  "section_title": "Başlık", "text": "Kanıt metni"}]},
        }],
    }
    questions = {
        "schema": "ogm-ayt-discovery-calibration-v1", "source_checksum": "questions-v1",
        "queries": [{"id": "q1", "topic": "Konu", "query": "Soru"}],
    }
    reviews = [{"candidate_id": "q1", "reviewed": True, "question_diagnosis": "candidate_set_insufficient"}]
    return corpus, questions, reviews


def test_supplementary_calibration_is_answer_free_and_review_only():
    result = build(*_inputs())

    assert result["runtime_enabled"] is False
    assert result["qlora_enabled"] is False
    assert result["selection"]["query_count"] == 1
    assert result["documents"][0]["review_route"] == "supplementary_pdf_crop_required"


def test_supplementary_calibration_rejects_an_enabled_source():
    corpus, questions, reviews = _inputs()
    corpus["books"][0]["student_runtime_eligible"] = True

    with pytest.raises(ValueError, match="açılamaz"):
        build(corpus, questions, reviews)
