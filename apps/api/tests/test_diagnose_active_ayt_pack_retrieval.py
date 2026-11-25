import copy
import json

import pytest

from app.pipeline.diagnose_active_ayt_pack_retrieval import build


def _inputs():
    source_checksum = "a" * 64
    evidence = {
        "source_id": "meb.pdf",
        "source_checksum": source_checksum,
        "page": 12,
        "bbox": [10.0, 10.0, 90.0, 40.0],
        "quote": "Ankara Büyük Millet Meclisi açıldı.",
        "role": "primary",
    }
    item = {
        "id": "atom-1",
        "page": 12,
        "bbox": [10.0, 10.0, 90.0, 40.0],
        "text": "Ankara Büyük Millet Meclisi 23 Nisan tarihinde açıldı.",
    }
    pack = {
        "schema": "ayt-history-exam-pack-v1",
        "sources": [{"id": "meb.pdf", "source_checksum": source_checksum}],
        "questions": [{
            "id": "question-1",
            "question": "Ankara Büyük Millet Meclisi ne zaman açıldı?",
            "topic": "Millî Mücadele",
            "choices": ["Ankara", "İstanbul", "İzmir", "Sivas", "Erzurum"],
            "evidence": [evidence],
        }],
    }
    index = {
        "chunks": [copy.deepcopy(item)],
        "context_chunks": [copy.deepcopy(item)],
        "evidence_atoms": [copy.deepcopy(item)],
    }
    corpus = {
        "schema": "multi-history-rag-v1",
        "corpus_checksum": "corpus-v1",
        "books": [{
            "source_name": "meb.pdf",
            "source_checksum": source_checksum,
            "index": index,
        }],
    }
    return pack, corpus


def test_diagnostic_is_aggregate_only_and_counts_bbox_match():
    pack, corpus = _inputs()
    result = build(pack, corpus)

    assert result["question_count"] == 1
    assert result["primary_evidence_count"] == 1
    assert result["runtime_enabled"] is False
    assert result["human_relevance_labels"] is False
    assert result["gold_label_kind"] == "primary_evidence_bbox_localization_proxy"
    assert "Ankara Büyük Millet Meclisi" not in json.dumps(result, ensure_ascii=False)
    context_result = next(row for row in result["results"]
                          if row["method"] == "context_chunks:question_plus_choices")
    assert context_result["bbox_mappable_questions"] == 1
    assert context_result["recall_3_all_questions"] == 1.0


def test_diagnostic_fails_closed_on_source_checksum_mismatch():
    pack, corpus = _inputs()
    corpus["books"][0]["source_checksum"] = "b" * 64

    with pytest.raises(ValueError, match="kaynak checksum"):
        build(pack, corpus)


def test_unmappable_evidence_is_counted_as_retrieval_miss():
    pack, corpus = _inputs()
    for kind in ("chunks", "context_chunks", "evidence_atoms"):
        corpus["books"][0]["index"][kind][0]["bbox"] = [200.0, 200.0, 250.0, 250.0]

    result = build(pack, corpus)

    context_result = next(row for row in result["results"]
                          if row["method"] == "context_chunks:question_plus_choices")
    assert context_result["bbox_mappable_questions"] == 0
    assert context_result["recall_3_all_questions"] == 0.0


def test_rrf_keeps_both_localizations_when_duplicate_text_has_distinct_boxes():
    pack, corpus = _inputs()
    for kind in ("chunks", "context_chunks"):
        corpus["books"][0]["index"][kind][0]["bbox"] = [200.0, 200.0, 250.0, 250.0]

    result = build(pack, corpus)

    rrf_result = next(row for row in result["results"] if row["method"] == "rrf_top20_each_top3")
    assert rrf_result["bbox_mappable_questions"] == 1
    assert rrf_result["complete_primary_bundle_at_3"] == 1.0
