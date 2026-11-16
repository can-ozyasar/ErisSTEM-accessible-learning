"""Section triage must stay answer-free and never approve questions."""

import pytest

from app.pipeline.triage_ayt_deneme_sections import build


def _payloads():
    question_checksum = "q" * 64
    book_checksum = "b" * 64
    corpus_checksum = "c" * 64
    question = {"parts": [{"text": "Amasya Genelgesi hangi olayla ilgilidir?"}],
                "choices": [{"label": "A", "text": "Amasya"}], "visuals": []}
    pool = {
        "schema": "ayt-target-question-candidates-v1",
        "source_checksum": question_checksum,
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "rows": [{"candidate_id": "q1", "source_checksum": question_checksum,
                  "page": 1, "question": question, "target_section_options": []}],
    }
    def atom(section_id, text):
        return {"id": f"atom-{section_id}", "section_id": section_id,
                "section_title": section_id, "heading": section_id, "page": 1,
                "bbox": [0, 0, 10, 10], "text": text,
                "quality": {"warnings": []},
                "pre_review": {"decision": "review_for_approval"}}
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": corpus_checksum,
              "books": [{"grade": 12, "source_checksum": book_checksum,
                         "source_name": "private.pdf",
                         "index": {"sections": [{"id": "2.1"}, {"id": "1.1"}],
                                   "evidence_atoms": [atom("2.1", "Amasya Genelgesi Millî Mücadele"),
                                                      atom("1.1", "Orta Çağ tarihi")],
                                   "context_chunks": []}}]}
    scope = {"grade": 12,
             "source_binding": {"corpus_checksum": corpus_checksum,
                                "meb_source_checksum": book_checksum},
             "sections": [{"section_id": "2.1"}]}
    return pool, corpus, scope


def test_triage_uses_stem_not_choices_and_does_not_approve():
    pool, corpus, scope = _payloads()
    alternative = {**pool["rows"][0], "candidate_id": "q2",
                   "question": {**pool["rows"][0]["question"],
                                "choices": [{"label": "A", "text": "Orta Çağ tarihi"}]}}
    pool["rows"].append(alternative)
    result = build(pool, corpus, scope)
    assert result["question_count"] == 2
    assert result["rows"][0]["section_proposals"] == result["rows"][1]["section_proposals"]
    assert result["rows"][0]["section_proposals"][0]["section_id"] == "2.1"
    assert result["runtime_enabled"] is False
    assert result["qlora_enabled"] is False
    assert "question" not in result["rows"][0]


def test_triage_rejects_stale_book_and_visual_question():
    pool, corpus, scope = _payloads()
    scope["source_binding"]["corpus_checksum"] = "x" * 64
    with pytest.raises(ValueError, match="checksum"):
        build(pool, corpus, scope)
    scope["source_binding"]["corpus_checksum"] = corpus["corpus_checksum"]
    pool["rows"][0]["question"]["visuals"] = [{"type": "image"}]
    with pytest.raises(ValueError, match="Görsel"):
        build(pool, corpus, scope)
