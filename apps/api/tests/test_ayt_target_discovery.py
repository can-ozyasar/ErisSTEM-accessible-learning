from app.pipeline.ayt_target_discovery import build


def _corpus():
    chunks = [{"id": "a", "section_id": "2.1"}, {"id": "b", "section_id": "9.9"}]
    return {
        "schema": "multi-history-rag-v1",
        "corpus_checksum": "corpus",
        "books": [{"grade": 12, "source_checksum": "meb", "index": {"chunks": chunks}}],
    }


def _scope():
    return {
        "schema": "ayt-target-scope-manifest-v1",
        "source_binding": {
            "corpus_checksum": "corpus",
            "meb_source_checksum": "meb",
            "scope_report_checksum": "scope",
        },
        "sections": [{"section_id": item} for item in ("1.3", "2.1", "2.4", "2.5", "3.1", "3.2")],
    }


def _transcriptions():
    return {
        "schema": "ogm-ayt-private-transcription-v1",
        "source_checksum": "questions",
        "rows": [
            {"candidate_id": "keep", "topic": "Millî Mücadele"},
            {"candidate_id": "drop", "topic": "II. Dünya Savaşı Sürecinde Türkiye ve Dünya"},
        ],
    }


def test_target_discovery_keeps_only_broad_topics_that_can_map_to_target_sections():
    pool, corpus = build(_transcriptions(), _scope(), _corpus())
    assert pool["candidate_count"] == 1
    assert pool["rows"][0]["candidate_id"] == "keep"
    assert [row["id"] for row in corpus["books"][0]["index"]["chunks"]] == ["a"]
    assert pool["qlora_enabled"] is False


def test_target_discovery_rejects_corpus_version_mismatch():
    bad = _corpus() | {"corpus_checksum": "different"}
    try:
        build(_transcriptions(), _scope(), bad)
    except ValueError as error:
        assert "eşleşmiyor" in str(error)
    else:
        raise AssertionError("checksum mismatch must fail closed")
