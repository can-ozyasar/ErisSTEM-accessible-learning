from app.pipeline.ogm_ayt_evidence_queue import _topic_pool, build


def test_evidence_queue_blocks_failed_transcription_without_querying_source():
    transcriptions = {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "q",
                      "rows": [{"candidate_id": "q1", "transcription_status": "rejected_incomplete_layout_bound_ocr"}]}
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": []}
    result = build(transcriptions, corpus)
    assert result["proposals"][0]["status"] == "blocked_transcription_quality"
    assert result["proposals"][0]["suggestions"] == []


def test_topic_pool_rejects_cross_period_section():
    pool = [({"grade": 12}, {"section_title": "MİLLÎ MÜCADELE’YE HAZIRLIK DÖNEMİ"}),
            ({"grade": 12}, {"section_title": "1990 SONRASINDA TÜRKİYE"})]
    result = _topic_pool(pool, "Millî Mücadele")
    assert len(result) == 1
    assert "MÜCADELE" in result[0][1]["section_title"]
