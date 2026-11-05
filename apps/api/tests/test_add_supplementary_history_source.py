import pytest

from app.pipeline.add_supplementary_history_source import build


def _corpus():
    return {
        "schema": "multi-history-rag-v1",
        "books": [{"source_checksum": "primary", "index_checksum": "index-primary"}],
    }


def test_supplementary_source_is_review_only(tmp_path, monkeypatch):
    source = tmp_path / "ozet.pdf"
    source.write_bytes(b"%PDF-1.7\nexample")
    monkeypatch.setattr(
        "app.pipeline.add_supplementary_history_source.build_index",
        lambda _source: {"source_checksum": "supplementary", "chunks": [{"id": "c1"}]},
    )

    result = build(_corpus(), source)

    added = result["books"][-1]
    assert added["source_role"] == "supplementary_candidate"
    assert added["student_runtime_eligible"] is False
    assert added["qlora_eligible"] is False
    assert result["corpus_checksum"]


def test_supplementary_source_rejects_non_pdf_and_duplicate(tmp_path, monkeypatch):
    source = tmp_path / "ozet.pdf"
    source.write_bytes(b"not a pdf")
    with pytest.raises(ValueError, match="PDF"):
        build(_corpus(), source)

    source.write_bytes(b"%PDF-1.7\nexample")
    monkeypatch.setattr(
        "app.pipeline.add_supplementary_history_source.build_index",
        lambda _source: {"source_checksum": "primary", "chunks": []},
    )
    with pytest.raises(ValueError, match="zaten"):
        build(_corpus(), source)
