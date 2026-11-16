from __future__ import annotations

from app.pipeline.audit_dort_dortluk_v6_citations import audit


def test_flags_support_quote_not_found_in_cited_chunk():
    corpus = {"corpus_checksum": "abc", "books": [{"index": {
        "chunks": [{"id": "right", "text": "Paris Konferansı'nda karar alındı."}],
        "context_chunks": [], "evidence_atoms": [],
    }}]}
    report = {"reviews": [{"candidate_id": "q1", "options": [{
        "label": "A", "verdict": "direct", "quote": "San Remo koşulları hazırlandı.",
        "evidence_chunk_ids": ["right"],
    }]}]}

    result = audit(corpus, [("agent_a", report)])

    assert result["supporting_option_citations_checked"] == 1
    assert result["citation_link_failures"] == 1
    assert result["failures"][0]["candidate_id"] == "q1"


def test_accepts_pdf_line_wrap_and_ignores_non_supporting_options():
    corpus = {"books": [{"index": {
        "chunks": [{"id": "right", "text": "Yunanistan, Türkiye'yi ziyaret etti."}],
        "context_chunks": [], "evidence_atoms": [],
    }}]}
    report = {"reviews": [{"candidate_id": "q1", "option_assessment": [
        {"label": "A", "verdict": "supports", "quote": "Yunanistan, Türki- ye'yi ziyaret etti.",
         "evidence_chunk_ids": ["right"]},
        {"label": "B", "verdict": "not_addressed", "quote": "unused", "evidence_chunk_ids": []},
    ]}]}

    result = audit(corpus, [("agent_b", report)])

    assert result["citation_link_failures"] == 0


def test_rebinds_stale_chunk_id_only_on_same_source_page():
    corpus = {"books": [{"source_name": "book.pdf", "source_checksum": "sum1", "index": {
        "chunks": [{"id": "current-id", "page": 29, "text": "İtalya taraf değiştirdi."}],
        "context_chunks": [], "evidence_atoms": [],
    }}]}
    report = {"reviews": [{"candidate_id": "q1", "cards": [{
        "chunk_id": "old-id", "source_checksum": "sum1", "page": 29,
        "source_name": "book.pdf",
    }], "options": [{
        "label": "A", "verdict": "direct", "quote": "İtalya taraf değiştirdi.",
        "evidence_chunk_ids": ["old-id"],
    }]}]}

    result = audit(corpus, [("agent_a", report)])

    assert result["citation_link_failures"] == 0
    assert result["stale_chunk_id_references"] == 1
    assert result["stale_reference_rebindings"][0]["current_chunk_ids"] == ["current-id"]
