from __future__ import annotations

import copy

import pytest

from app.pipeline.audit_dort_dortluk_v10_delta_review import merge


def _side(partition: str, candidate_id: str, chunk_id: str):
    checksum = "a" * 64
    card = {
        "chunk_id": chunk_id,
        "source_checksum": checksum,
        "source_page": 12,
        "crop": f"crops/{chunk_id}.png",
    }
    pack_row = {
        "candidate_id": candidate_id,
        "question_source_pdf_page": 2,
        "new_evidence_cards": [card],
    }
    pack = {
        "review_partition": partition,
        "review_scope": "new_delta_only",
        "source_checksum": "b" * 64,
        "corpus_checksum": "c" * 64,
        "question_source_checksum": "b" * 64,
        "question_count": 1,
        "reviews": [pack_row],
        **{flag: False for flag in (
            "answer_key_accessed", "worked_explanation_accessed", "teacher_approval",
            "runtime_enabled", "qlora_enabled", "kaggle_enabled",
        )},
    }
    review_row = {
        "candidate_id": candidate_id,
        "question_source_pdf_page": 2,
        "question_source_page_visual_checked": True,
        "visual_independence": "text_only",
        "delta_decision": "partial",
        "review_decision": "partial",
        "visually_checked_chunk_ids": [chunk_id],
        "visually_checked_crop_count": 1,
        "useful_chunk_ids": [chunk_id],
        "supporting_chunk_ids": [chunk_id],
        "evidence": [{
            "chunk_id": chunk_id,
            "source_checksum": checksum,
            "page": 12,
            "quote": "Kuzey Makedonya ilişkisi",
            "claim_supported": "Bir kısmi ilişkiyi gösterir.",
            "quote_visual_verified": True,
        }],
        "unsupported_claims": ["Diğer seçenekler"],
        "reason": "Kısmi kanıt.",
    }
    report = {
        "source_checksum": "b" * 64,
        "corpus_checksum": "c" * 64,
        "question_source_checksum": "b" * 64,
        "question_count": 1,
        "visually_checked_crop_count": 1,
        "visually_checked_question_page_count": 1,
        "all_question_source_pages_visually_checked": True,
        "reviews": [review_row],
        **{flag: False for flag in (
            "answer_key_accessed", "worked_explanation_accessed", "teacher_approval",
            "runtime_enabled", "qlora_enabled", "kaggle_enabled",
        )},
    }
    return pack, report


def _inputs():
    pack_a, report_a = _side("agent-a", "q-a", "chunk-a")
    pack_b, report_b = _side("agent-b", "q-b", "chunk-b")
    queue = {
        "retrieval_strategy": "claimwise_option_reserve",
        "source_checksum": "b" * 64,
        "corpus_checksum": "c" * 64,
        "proposals": [
            {"candidate_id": candidate_id, "suggestions": [{
                "chunk_id": chunk_id,
                "source_checksum": "a" * 64,
                "page": 12,
                "text": "Kuzey Makedonya ilişkisi açıkça yazıyor.",
            }]}
            for candidate_id, chunk_id in (("q-a", "chunk-a"), ("q-b", "chunk-b"))
        ],
    }
    return pack_a, pack_b, report_a, report_b, queue


def test_merges_two_blind_delta_partitions_after_provenance_checks():
    result = merge(*_inputs())

    assert result["question_count"] == 2
    assert result["delta_decision_counts"] == {"partial": 2}
    assert result["teacher_approval"] is False
    assert result["runtime_enabled"] is False


def test_rejects_quote_not_found_in_candidate_source_text():
    inputs = list(_inputs())
    inputs[2] = copy.deepcopy(inputs[2])
    inputs[4] = copy.deepcopy(inputs[4])
    inputs[4]["proposals"][0]["suggestions"][0]["text"] = "Başka içerik"
    inputs[2]["reviews"][0]["evidence"][0]["quote_visual_verified"] = False

    with pytest.raises(ValueError, match="görsel olarak doğrulanmalı"):
        merge(*inputs)


def test_rejects_missing_visual_crop_review():
    inputs = list(_inputs())
    inputs[2] = copy.deepcopy(inputs[2])
    inputs[2]["reviews"][0]["visually_checked_chunk_ids"] = []

    with pytest.raises(ValueError, match="her yeni crop tek tek kontrol edilmeli"):
        merge(*inputs)


def test_records_visually_confirmed_source_text_alignment_gap():
    inputs = list(_inputs())
    inputs[2] = copy.deepcopy(inputs[2])
    inputs[2]["reviews"][0]["evidence"][0]["quote"] = "Metinde olmayan ama crop'ta görünen ifade"

    result = merge(*inputs)

    assert result["source_text_alignment_issue_count"] == 1
    row = next(row for row in result["reviews"] if row["candidate_id"] == "q-a")
    assert row["source_text_alignment_issue"] is True
    assert result["runtime_enabled"] is False


def test_merges_atom_context_option_reserve_delta_without_opening_product_gates():
    inputs = list(_inputs())
    inputs[4] = copy.deepcopy(inputs[4])
    inputs[4]["retrieval_strategy"] = "claimwise_atom_context_option_reserve"

    result = merge(*inputs)

    assert result["schema"] == "dort-dortluk-claimwise_atom_context_option_reserve-delta-review-merged-v1"
    assert result["qlora_enabled"] is False
