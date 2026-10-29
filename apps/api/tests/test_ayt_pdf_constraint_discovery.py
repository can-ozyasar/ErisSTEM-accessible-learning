import hashlib

import pymupdf

from app.pipeline.ayt_pdf_constraint_discovery import build


def test_raw_pdf_discovery_finds_short_or_quoted_relation_for_review(tmp_path):
    pdf_path = tmp_path / "history.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50, 80), '"Hakanin esi hatun devlet islerinde soz sahibiydi."')
    document.save(pdf_path)
    document.close()
    checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "corpus-v1", "books": [{
        "grade": 9, "source_name": pdf_path.name, "source_checksum": checksum,
        "index": {"sections": [{"id": "1.1", "title": "Türk tarihi", "start": 1, "end": 1}]},
    }]}
    constraints = {"schema": "ayt-evidence-constraints-v1", "question_source_checksum": "questions-v1",
                   "corpus_checksum": "corpus-v1", "cases": [{"candidate_id": "q1", "exam_year": 2024,
                   "query_terms": ["hatun hakan"], "required_clauses": [
                       {"id": "hatun-hukumdar", "all_of": ["hatun"], "any_of": ["hakan"]},
                   ]}]}
    result = build(corpus, constraints, tmp_path)
    row = result["proposals"][0]
    assert row["status"] == "teacher_review_required"
    assert row["suggestions"][0]["raw_pdf_fallback"] is True
    assert "no output is approved" in result["notice"]
