import pytest

from app.pipeline.validate_ogm_source_grounded_pilot import validate


def _fixtures():
    review = {"is_human_teacher_approval": False, "reviews": [{"candidate_id": "q1", "candidates": [
        {"id": "e1", "verdict": "support"}]}]}
    answers = {"source_checksum": "question-pdf", "records": [{"candidate_id": "q1", "correct_choice": "A"}]}
    readiness = {"source_checksum": "question-pdf", "approved_transcription_candidates": [{"id": "q1"}]}
    package = {"schema": "ogm-ayt-history-source-grounded-pilot-candidates-v1", "runtime_enabled": False,
               "source_checksum": "question-pdf", "candidate_count": 1, "maximum_evidence_items": 3,
               "questions": [{"candidate_id": "q1", "correct_choice": "A",
                              "answer_key_source": {"source_checksum": "question-pdf"},
                              "evidence_bundle": [{"id": "e1", "source_name": "MEB", "source_checksum": "book",
                                                   "page": 1, "bbox": [1, 2, 3, 4], "excerpt": "kanıt"}]}]}
    return package, review, answers, readiness


def test_validates_auditable_non_runtime_candidate_package():
    assert validate(*_fixtures())["valid"] is True


def test_rejects_unreviewable_evidence():
    package, review, answers, readiness = _fixtures()
    package["questions"][0]["evidence_bundle"][0]["id"] = "not-supported"
    with pytest.raises(ValueError, match="denetlenemeyen"):
        validate(package, review, answers, readiness)
