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
    assert not generic["lexical_overlap_hint"]
    assert direct["lexical_overlap_hint"]


def test_queue_does_not_invent_candidate_when_no_term_matches():
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
    assert proposal["status"] == "insufficient_evidence"
    assert proposal["suggestions"] == []


def test_queue_expands_across_books_and_preserves_duplicate_chunk_ids():
    row = {"candidate_id": "q1", "topic": "Millî Mücadele",
           "transcription_status": "private_teacher_review_required",
           "question": {"stem": "Lozan görüşmelerinde kapitülasyonlar nasıl ele alındı?", "choices": []}}

    def book(grade, checksum, section, text):
        return {"grade": grade, "source_name": f"grade-{grade}.pdf", "source_checksum": checksum,
                "index": {"chunks": [{"id": "shared-id", "page": 10, "bbox": [0, 0, 1, 1],
                                      "section_title": section, "text": text,
                                      "pre_review": {"decision": "review_for_approval"},
                                      "quality": {"warnings": []}}]}}

    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": [
        book(12, "s12", "MİLLÎ MÜCADELE", "Lozan sürecinde görüşmeler sürdü."),
        book(11, "s11", "OSMANLI DİPLOMASİSİ", "Lozan görüşmelerinde kapitülasyonlar ele alındı."),
    ]}
    queue = build({"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "q", "rows": [row]},
                  corpus, limit=2)
    proposal = queue["proposals"][0]
    assert proposal["expanded_to_other_sections"] is True
    assert [(item["grade"], item["chunk_id"], item["source_checksum"])
            for item in proposal["suggestions"]] == [(12, "shared-id", "s12"), (11, "shared-id", "s11")]
    assert all(item["review_status"] == "candidate_unverified" for item in proposal["suggestions"])
