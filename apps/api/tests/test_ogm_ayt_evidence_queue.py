from app.pipeline.ogm_ayt_evidence_queue import _claim_coverage, _topic_pool, build


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


def test_claim_coverage_requires_a_distinctive_root_term():
    row = {"question": {"stem": "Lozan Antlaşması sonrasında hangi gelişme yaşanmıştır?",
                        "choices": []}}
    generic = _claim_coverage(row, "Millî Mücadele sonrasında Türkiye'de yeni bir dönem başladı.")
    direct = _claim_coverage(row, "Lozan Antlaşması ile Türkiye'nin bağımsızlığı uluslararası alanda tanındı.")
    assert not generic["literal_claim_gate"]
    assert direct["literal_claim_gate"]


def test_queue_marks_generic_topic_context_for_reretrieval():
    transcriptions = {
        "schema": "ogm-ayt-private-transcription-v1", "source_checksum": "q",
        "rows": [{
            "candidate_id": "q1", "topic": "Millî Mücadele",
            "transcription_status": "private_teacher_review_required",
            "question": {"stem": "Lozan Antlaşması sonrasında hangi gelişme yaşanmıştır?",
                         "choices": [{"text": "Birinci ifade"}, {"text": "İkinci ifade"}]},
        }],
    }
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": [{
        "grade": 12, "source_name": "MEB", "source_checksum": "m", "index": {"chunks": [{
            "id": "generic", "page": 10, "bbox": [0, 0, 1, 1],
            "section_title": "MİLLÎ MÜCADELE", "text": "Millî Mücadele Türkiye tarihinde önemlidir.",
            "pre_review": {"decision": "review_for_approval"}, "quality": {"warnings": []},
        }]},
    }]}
    result = build(transcriptions, corpus)
    proposal = result["proposals"][0]
    assert proposal["status"] == "reretrieve_claim_coverage"
    assert proposal["suggestions"] == []
