import pytest

from app.pipeline.ogm_ayt_discovery_calibration import build


def _transcriptions():
    return {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "questions", "rows": [
        {"candidate_id": "one", "topic": "A", "transcription_status": "private_teacher_review_required",
         "question": {"stem": "Kök", "choices": [{"text": "Şık"}]}},
        {"candidate_id": "two", "topic": "B", "transcription_status": "private_teacher_review_required",
         "question": {"stem": "Kök 2", "choices": []}},
    ]}


def _gold():
    return {"schema": "ogm-ayt-retrieval-gold-v1", "source_checksum": "questions", "corpus_checksum": "corpus",
            "cases": [
                {"candidate_id": "one", "reviewed": True, "coverage_complete": True, "abstain": True},
                {"candidate_id": "two", "reviewed": True, "coverage_complete": True, "abstain": False},
            ]}


def _corpus():
    return {"schema": "multi-history-rag-v1", "corpus_checksum": "corpus", "books": [
        {"source_checksum": "book", "grade": 12, "index": {"chunks": [
            {"id": "kept", "page": 1, "bbox": [], "section_title": "Başlık", "text": "Metin",
             "pre_review": {"decision": "manual_review"}},
            {"id": "removed", "page": 2, "bbox": [], "section_title": "Başlık", "text": "Metin",
             "pre_review": {"decision": "do_not_use"}},
        ]}},
    ]}


def _split():
    return {"schema": "ogm-ayt-qlora-staging-split-v1", "splits": {"one": "dev", "two": "sealed_test"}}


def test_calibration_uses_only_prior_abstentions_and_keeps_manual_review_documents():
    result = build(_transcriptions(), _gold(), _corpus(), _split())
    assert [query["id"] for query in result["queries"]] == ["one"]
    assert [document["chunk_id"] for document in result["documents"]] == ["kept"]
    assert "answer" not in result


def test_calibration_rejects_answer_bearing_input():
    transcriptions = _transcriptions()
    transcriptions["answer_key"] = "A"
    with pytest.raises(ValueError, match="cevap anahtarı"):
        build(transcriptions, _gold(), _corpus(), _split())


def test_calibration_never_exports_a_sealed_test_question():
    gold = _gold()
    gold["cases"][1]["abstain"] = True
    result = build(_transcriptions(), gold, _corpus(), _split())
    assert [query["id"] for query in result["queries"]] == ["one"]
