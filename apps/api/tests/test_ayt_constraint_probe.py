import pytest

from app.pipeline.ayt_constraint_probe import _rank_matches, build


def _chunk(chunk_id: str, text: str) -> dict:
    return {
        "id": chunk_id, "section_id": "1.1", "section_title": "Türk tarihi", "page": 8,
        "bbox": [1, 2, 3, 4], "text": text,
        "pre_review": {"decision": "review_for_approval"},
    }


def _inputs():
    questions = {"schema": "ayt-tarih2-candidates-v1", "source_checksum": "questions-v1", "candidates": [{
        "candidate_id": "q1", "exam_year": 2024, "year_status": "bound",
    }]}
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "corpus-v1", "books": [{
        "grade": 9, "source_name": "history.pdf", "source_checksum": "book-v1",
        "index": {"chunks": [_chunk("relation", "Türgişler Emevilerle mücadele etti."),
                             _chunk("battle", "Karluklar Talas Savaşı'nda yer aldı.")]},
    }]}
    constraints = {"schema": "ayt-evidence-constraints-v1", "question_source_checksum": "questions-v1",
                   "corpus_checksum": "corpus-v1", "cases": [{"candidate_id": "q1",
                   "query_terms": ["Türgiş Karluk Talas"], "required_clauses": [
                       {"id": "turges-emevi", "all_of": ["Türgiş", "Emevi"]},
                       {"id": "karluk-talas", "all_of": ["Karluk", "Talas"]},
                   ]}]}
    return questions, corpus, constraints


def test_constraint_probe_requires_every_relation_before_review():
    questions, corpus, constraints = _inputs()
    result = build(questions, corpus, constraints)
    row = result["proposals"][0]
    assert row["status"] == "teacher_review_required"
    assert row["constraint_gate"] == {"required_clause_ids": ["turges-emevi", "karluk-talas"],
                                       "missing_clause_ids": [], "complete": True}
    assert {item["constraint_clause_id"] for item in row["suggestions"]} == {"turges-emevi", "karluk-talas"}
    assert "not an evidence approval" in result["notice"]


def test_constraint_probe_abstains_when_one_relation_is_missing():
    questions, corpus, constraints = _inputs()
    corpus["books"][0]["index"]["chunks"] = corpus["books"][0]["index"]["chunks"][:1]
    result = build(questions, corpus, constraints)
    row = result["proposals"][0]
    assert row["status"] == "insufficient_evidence"
    assert row["constraint_gate"]["missing_clause_ids"] == ["karluk-talas"]


def test_manual_review_sources_need_an_explicit_discovery_opt_in():
    questions, corpus, constraints = _inputs()
    for chunk in corpus["books"][0]["index"]["chunks"]:
        chunk["pre_review"]["decision"] = "manual_review"
    assert build(questions, corpus, constraints)["proposals"][0]["status"] == "insufficient_evidence"
    discovered = build(questions, corpus, constraints, include_manual_review=True)
    assert discovered["proposals"][0]["status"] == "teacher_review_required"
    assert "discovery only" in discovered["notice"]


def test_constraint_ranker_keeps_review_candidates_page_diverse():
    book = {"source_checksum": "book-v1"}
    clause = {"all_of": ["hatun"]}
    chunks = [
        (book, _chunk("first", "Hatun devlet işlerinde etkiliydi.") | {"page": 4}),
        (book, _chunk("same-page", "Hatun kağanın eşiydi.") | {"page": 4}),
        (book, _chunk("other-page", "Hatun hükümdarın yanında yer aldı.") | {"page": 5}),
    ]
    assert [chunk["id"] for _, chunk in _rank_matches(chunks, clause, ["hatun"], 2)] == ["first", "other-page"]


def test_constraint_probe_keeps_all_clause_labels_for_one_passage():
    questions, corpus, constraints = _inputs()
    corpus["books"][0]["index"]["chunks"] = [_chunk("both", "Türgişler Emevilerle mücadele etti.")]
    constraints["cases"][0]["required_clauses"] = [
        {"id": "turges", "all_of": ["Türgiş"]},
        {"id": "emevi", "all_of": ["Emevi"]},
    ]
    row = build(questions, corpus, constraints)["proposals"][0]
    assert row["suggestions"][0]["constraint_clause_ids"] == ["turges", "emevi"]


def test_constraint_probe_rejects_wrong_checksum():
    questions, corpus, constraints = _inputs()
    constraints["corpus_checksum"] = "wrong"
    with pytest.raises(ValueError, match="corpus checksum"):
        build(questions, corpus, constraints)
