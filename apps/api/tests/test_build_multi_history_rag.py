from pathlib import Path

from app.pipeline import build_multi_history_rag as corpus_builder


def test_corpus_checksum_changes_when_the_extraction_policy_output_changes(monkeypatch):
    index = {
        "schema": 1, "policy_version": "source-type-v2", "source_checksum": "book-v1",
        "source_name": "history.pdf", "sections": [], "chunks": [], "exclusions": {},
    }
    monkeypatch.setattr(corpus_builder, "build_index", lambda _path: index)
    first = corpus_builder.build({9: Path("history.pdf")})
    index["policy_version"] = "source-type-v3"
    second = corpus_builder.build({9: Path("history.pdf")})
    assert first["books"][0]["source_checksum"] == second["books"][0]["source_checksum"]
    assert first["books"][0]["index_checksum"] != second["books"][0]["index_checksum"]
    assert first["corpus_checksum"] != second["corpus_checksum"]
