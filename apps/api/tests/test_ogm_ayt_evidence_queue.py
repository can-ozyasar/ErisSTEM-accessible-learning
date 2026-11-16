import pytest

from app.pipeline.ogm_ayt_evidence_queue import (
    _claim_coverage,
    _claim_queries,
    _eligible,
    _reserve_cross_section_candidates,
    _reserve_option_channel_candidates,
    _topic_pool,
    build,
)


def test_evidence_queue_blocks_failed_transcription_without_querying_source():
    transcriptions = {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "q",
                      "rows": [{"candidate_id": "q1", "transcription_status": "rejected_incomplete_layout_bound_ocr"}]}
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": []}
    result = build(transcriptions, corpus)
    assert result["proposals"][0]["status"] == "blocked_transcription_quality"
    assert result["proposals"][0]["suggestions"] == []


def test_private_review_queue_includes_clean_manual_review_but_excludes_risky_chunks():
    def chunk(identifier, decision, **quality):
        return {
            "id": identifier,
            "text": "Türkiye Boğazların yeniden görüşülmesini istedi.",
            "pre_review": {"decision": decision},
            "quality": {"text_quality": "clean", "warnings": [], **quality},
        }

    corpus = {"books": [{"grade": 12, "index": {"chunks": [
        chunk("approved_candidate", "review_for_approval"),
        chunk("context_review", "manual_review"),
        chunk("visual", "manual_review", visual_or_caption_risk=True),
        chunk("ocr", "manual_review", ocr_fragment_risk=True),
        chunk("bad_text", "manual_review", text_quality="degraded"),
    ]}}]}
    rows = _eligible(corpus)
    assert [item["id"] for _, item in rows] == ["approved_candidate", "context_review"]


def test_atom_experiment_adds_clean_evidence_atoms_without_changing_default_pool():
    record = {
        "id": "short-fact",
        "text": "Lozan görüşmelerinde kapitülasyonların kaldırılması kabul edildi.",
        "page": 10,
        "bbox": [1, 2, 30, 40],
        "section_title": "MİLLÎ MÜCADELE",
        "heading": "Lozan",
        "extraction_method": "standalone_fact",
        "pre_review": {"decision": "manual_review"},
        "quality": {"text_quality": "clean", "warnings": []},
    }
    corpus = {"books": [{"grade": 12, "index": {
        "chunks": [], "evidence_atoms": [record],
    }}]}

    assert _eligible(corpus) == []
    expanded = _eligible(corpus, include_atoms=True)
    assert expanded[0][1]["_index_layer"] == "evidence_atom"
    assert expanded[0][1]["extraction_method"] == "standalone_fact"


def test_topic_pool_rejects_cross_period_section():
    pool = [({"grade": 12}, {"section_title": "MİLLÎ MÜCADELE’YE HAZIRLIK DÖNEMİ"}),
            ({"grade": 12}, {"section_title": "1990 SONRASINDA TÜRKİYE"})]
    result = _topic_pool(pool, "Millî Mücadele")
    assert len(result) == 1
    assert "MÜCADELE" in result[0][1]["section_title"]


def test_target_topics_do_not_expand_to_generic_osmanli_headings():
    pool = [
        ({"grade": 12}, {"section_title": "I. DÜNYA SAVAŞI SÜRECİNDE OSMANLI DEVLETİ"}),
        ({"grade": 11}, {"section_title": "1789-1908 Yılları Arasında Osmanlı Devleti"}),
        ({"grade": 12}, {"section_title": "I. DÜNYA SAVAŞI’NIN SONUÇLARI"}),
        ({"grade": 11}, {"section_title": "1908-1918 Yılları Arasında Osmanlı Devleti’nde Meydana Gelen Siyasi ve Askerî Gelişmeler"}),
    ]
    result = _topic_pool(pool, "I. Dünya Savaşı Sürecinde Osmanlı Devleti")
    assert [book["grade"] for book, _ in result] == [12, 11]


def test_target_topics_include_historical_heading_alias_without_generic_expansion():
    pool = [
        ({"grade": 11}, {"section_title": "1908-1918 Yılları Arasında Osmanlı Devleti’nde Meydana Gelen Siyasi ve Askerî Gelişmeler"}),
        ({"grade": 11}, {"section_title": "1789-1908 Yılları Arasında Osmanlı Devleti’nde Meydana Gelen Siyasi, Askerî ve İdari Gelişmeler"}),
    ]
    assert len(_topic_pool(pool, "I. Dünya Savaşı Sürecinde Osmanlı Devleti")) == 1


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
            "pre_review": {"decision": "review_for_approval"},
            "quality": {"text_quality": "clean", "warnings": []},
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
                                      "quality": {"text_quality": "clean", "warnings": []}}]}}

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


def test_review_slate_reserves_cross_section_slots_when_topic_pool_is_full():
    local = [{"id": f"local-{i}", "in_topic_section": True} for i in range(5)]
    expanded = [{"id": f"other-{i}", "in_topic_section": False} for i in range(4)]
    selected = _reserve_cross_section_candidates(local, expanded, limit=3)
    assert [item["id"] for item in selected] == ["local-0", "local-1", "other-0"]

    assert _reserve_cross_section_candidates(local, [], limit=3) == local[:3]
    assert _reserve_cross_section_candidates([], expanded, limit=3) == expanded[:3]


def test_option_reserve_preserves_strong_single_channel_hit_and_balances_options():
    def candidate(identifier, *, score, channel, rank, scoped):
        return {
            "id": identifier,
            "_rrf_score": score,
            "_channel_ranks": [{"channel": channel, "rank": rank}],
            "in_topic_section": scoped,
        }

    # This candidate is only a rank-3 hit for option C, so a multi-channel
    # additive RRF can bury it under generic passages that match many queries.
    local = [
        candidate("generic", score=0.20, channel="whole_question", rank=1, scoped=True),
        candidate("option-a", score=0.12, channel="choice:A", rank=1, scoped=True),
        candidate("option-b", score=0.11, channel="choice:B", rank=1, scoped=True),
        candidate("option-c", score=0.02, channel="choice:C", rank=3, scoped=True),
    ]
    queries = [("choice:A", "A"), ("choice:B", "B"), ("choice:C", "C")]

    selected = _reserve_option_channel_candidates(local, [], queries, limit=4)

    assert [item["id"] for item in selected[:3]] == ["option-a", "option-b", "option-c"]
    assert selected[2]["_selection_reason"] == "reserved_choice:C"
    assert "generic" in {item["id"] for item in selected}


def test_option_reserve_keeps_one_cross_section_hit_when_it_is_option_specific():
    local = [{
        "id": "local-generic", "_rrf_score": 0.3,
        "_channel_ranks": [{"channel": "whole_question", "rank": 1}],
    }]
    expanded = [{
        "id": "other-section-option-hit", "_rrf_score": 0.01,
        "_channel_ranks": [{"channel": "choice:B", "rank": 2}],
    }]
    selected = _reserve_option_channel_candidates(
        local, expanded, [("choice:A", "A"), ("choice:B", "B")], limit=2
    )
    assert [item["id"] for item in selected] == ["other-section-option-hit", "local-generic"]
    assert selected[0]["_selection_reason"] == "reserved_choice:B"


def test_option_reserve_small_slate_considers_cross_section_before_later_local_options():
    local = [
        {"id": "local-a", "_rrf_score": 0.2,
         "_channel_ranks": [{"channel": "choice:A", "rank": 1}]},
        {"id": "local-c", "_rrf_score": 0.1,
         "_channel_ranks": [{"channel": "choice:C", "rank": 1}]},
    ]
    expanded = [{
        "id": "expanded-b", "_rrf_score": 0.01,
        "_channel_ranks": [{"channel": "choice:B", "rank": 1}],
    }]

    selected = _reserve_option_channel_candidates(
        local, expanded,
        [("choice:A", "A"), ("choice:B", "B"), ("choice:C", "C")],
        limit=2,
    )

    assert [item["id"] for item in selected] == ["local-a", "expanded-b"]


def test_claim_queries_give_each_option_a_separate_equal_channel():
    row = {"question": {"stem": "Hangi gelişme 1914 yılında yaşanmıştır?", "choices": [
        {"label": "A", "text": "Sarıkamış Harekâtı başladı."},
        {"label": "B", "text": "Saltanat kaldırıldı."},
    ]}}
    labels = [label for label, _ in _claim_queries(row)]
    assert labels == ["whole_question", "stem", "choice:A", "claim:A", "choice:B", "claim:B"]
    claim_a = dict(_claim_queries(row))["claim:A"]
    assert "1914" in claim_a and "Sarıkamış" in claim_a


def test_query_aliases_only_expand_search_text_without_changing_source_approval():
    row = {"question": {"stem": "Türkiye’nin öncülük ettiği antlaşmalardan hangisi?", "choices": [
        {"label": "A", "text": "Montrö Boğazlar Sözleşmesi"},
        {"label": "B", "text": "Lozan Barış Antlaşması"},
    ]}}
    queries = dict(_claim_queries(row))
    assert "montreux" in queries["choice:A"].casefold()
    assert "teklif" in queries["claim:A"]
    assert "review_for_approval" not in queries["claim:A"]


@pytest.mark.parametrize("strategy", [
    "claimwise_rrf", "claimwise_option_reserve", "claimwise_atom_context_option_reserve"
])
def test_claimwise_retrieval_keeps_option_specific_evidence_traceable(strategy):
    row = {"candidate_id": "q1", "topic": "I. Dünya Savaşı Sürecinde Osmanlı Devleti",
           "transcription_status": "private_teacher_review_required",
           "question": {"stem": "Hangi gelişme 1914 yılında yaşanmıştır?", "choices": [
               {"label": "A", "text": "Sarıkamış Harekâtı başladı."},
               {"label": "B", "text": "Saltanat kaldırıldı."},
           ]}}

    def chunk(identifier, text):
        return {"id": identifier, "page": 20, "bbox": [0, 0, 1, 1],
                "section_title": "I. DÜNYA SAVAŞI SÜRECİNDE OSMANLI DEVLETİ", "text": text,
                "pre_review": {"decision": "review_for_approval"},
                "quality": {"text_quality": "clean", "warnings": []}}

    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": [{
        "grade": 12, "source_name": "MEB", "source_checksum": "m", "index": {"chunks": [
            chunk("sarikamis", "22 Aralık 1914 tarihinde Sarıkamış Harekâtı başladı."),
            chunk("saltanat", "Saltanatın kaldırılması Cumhuriyet döneminde gerçekleşti."),
        ]},
    }]}
    result = build({"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "q",
                    "rows": [row]}, corpus, limit=2, strategy=strategy)
    proposal = result["proposals"][0]
    assert result["retrieval_strategy"] == strategy
    sarikamis = next(item for item in proposal["suggestions"] if item["chunk_id"] == "sarikamis")
    assert {rank["channel"] for rank in sarikamis["retrieval_channels"]} >= {"choice:A"}
    assert sarikamis["review_status"] == "candidate_unverified"
    if strategy == "claimwise_option_reserve":
        assert sarikamis["selection_reason"] == "reserved_choice:A"


def test_atom_context_strategy_retrieves_a_fact_from_atom_index():
    row = {"candidate_id": "q1", "topic": "I. Dünya Savaşı Sürecinde Osmanlı Devleti",
           "transcription_status": "private_teacher_review_required",
           "question": {"stem": "Lozan görüşmelerinde kapitülasyonların kaldırılması nasıl sonuçlandı?",
               "choices": [
                   {"label": "A", "text": "Kapitülasyonların kaldırılması kabul edildi."},
                   {"label": "B", "text": "Kapitülasyonlar sürdürüldü."},
               ]}}

    atom = {
        "id": "short-fact", "page": 20, "bbox": [0, 0, 100, 20],
        "section_id": "s1", "section_title": "MİLLÎ MÜCADELE", "heading": "Lozan",
        "text": "Lozan görüşmelerinde kapitülasyonların kaldırılması kabul edildi.",
        "extraction_method": "standalone_fact",
        "pre_review": {"decision": "review_for_approval"},
        "quality": {"text_quality": "clean", "warnings": []},
    }
    context = {
        "id": "broad-context", "page": 20, "bbox": [0, 30, 100, 80],
        "section_id": "s1", "section_title": "MİLLÎ MÜCADELE",
        "text": "Millî Mücadele döneminde çeşitli gelişmeler yaşandı.",
        "pre_review": {"decision": "review_for_approval"},
        "quality": {"text_quality": "clean", "warnings": []},
    }
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "c", "books": [{
        "grade": 12, "source_name": "MEB", "source_checksum": "m",
        "index": {"chunks": [context], "evidence_atoms": [atom]},
    }]}

    result = build({"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "q",
                    "rows": [row]}, corpus, limit=2,
                   strategy="claimwise_atom_context_option_reserve")

    atom_suggestion = next(item for item in result["proposals"][0]["suggestions"]
                           if item["chunk_id"] == "short-fact")
    assert atom_suggestion["index_layer"] == "evidence_atom"
    assert atom_suggestion["heading"] == "Lozan"
