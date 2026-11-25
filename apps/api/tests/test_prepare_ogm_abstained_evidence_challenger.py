import pytest

from app.pipeline.prepare_ogm_abstained_evidence_challenger import build


def _inputs():
    question_checksum, corpus_checksum = "q" * 64, "c" * 64
    candidate_id = "ogm-ayt-deneme:q:d1:p1:q1"
    questions = {
        "schema": "ayt-target-question-candidates-v1", "source_checksum": question_checksum,
        "rows": [{"candidate_id": candidate_id, "deneme_number": 1, "question": {"number": 1,
                  "parts": [{"text": "Yazıyı ilk kullanan uygarlık hangisidir?"}],
                  "choices": [{"label": label, "text": text} for label, text in zip("ABCDE", ["Sümer", "Hitit", "Frig", "Lidya", "Urartu"])]}}],
    }
    readiness = {"schema": "ogm-ayt-real-question-pilot-readiness-v1", "source_checksum": question_checksum,
                 "approved_transcription_candidates": [{"id": candidate_id}]}
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": corpus_checksum, "books": [{
        "source_role": "primary", "source_checksum": "b" * 64, "source_name": "meb.pdf", "grade": 9,
        "index": {"evidence_atoms": [{"id": "a1", "section_id": "1", "section_title": "İlk Çağ", "page": 1,
                                      "bbox": [1, 1, 2, 2], "text": "Sümerler yazıyı kullandı.", "quality": {}, "pre_review": {"decision": "manual_review"}}],
                  "context_chunks": []},
    }]}
    prior = {"schema": "ogm-ayt-real-question-evidence-pdf-review-v1", "question_source_checksum": question_checksum,
             "corpus_checksum": corpus_checksum, "reviews": [{"candidate_id": candidate_id, "status": "ai_consensus_abstain"}]}
    return questions, readiness, corpus, prior


def test_creates_answer_free_challenger_for_abstained_question():
    result = build(*_inputs())
    assert result["question_count"] == 1
    assert result["retrieval"]["answer_key_used"] is False
    assert result["runtime_enabled"] is False
    assert result["proposals"][0]["suggestions"][0]["id"].endswith(":atom:a1")


def test_refuses_a_corpus_or_checksum_mismatch():
    questions, readiness, corpus, prior = _inputs()
    prior["corpus_checksum"] = "x" * 64
    with pytest.raises(ValueError, match="corpus sürümü"):
        build(questions, readiness, corpus, prior)
