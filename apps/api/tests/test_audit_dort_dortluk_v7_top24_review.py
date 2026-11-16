from __future__ import annotations

import pytest

from app.pipeline.audit_dort_dortluk_v7_top24_review import merge


def fixtures(question_count=89, crops_per_question=12):
    ids = [f"q{i:03d}" for i in range(question_count)]
    packs = []
    reports = []
    proposals = []
    midpoint = (question_count + 1) // 2
    for partition_ids in (ids[:midpoint], ids[midpoint:]):
        pack_reviews = []
        review_rows = []
        for candidate_id in partition_ids:
            cards = [{
                "chunk_id": f"chunk-{candidate_id}-{rank}",
                "source_checksum": "a" * 64,
                "source_page": 12,
            } for rank in range(crops_per_question)]
            card = cards[0]
            pack_reviews.append({
                "candidate_id": candidate_id,
                "new_evidence_cards": cards,
            })
            review_rows.append({
                "candidate_id": candidate_id,
                "final_decision": "direct",
                "visual_independence": "text_only",
                "visually_checked_chunk_ids": [c["chunk_id"] for c in cards],
                "relevant_chunk_ids": [cards[0]["chunk_id"]],
                "irrelevant_chunk_ids": [c["chunk_id"] for c in cards[1:]],
                "visual_scope_reason": "Question is text only.",
                "supporting_chunk_ids": [card["chunk_id"]],
                "evidence": [{
                    "chunk_id": card["chunk_id"],
                    "source_checksum": "a" * 64,
                    "page": 12,
                    "quote": "The treaty was signed in 1923.",
                    "claim_supported": "The question asks when the treaty was signed.",
                }],
                "unsupported_claims": [],
                "reason": "The cited sentence states the requested fact.",
            })
            proposals.append({
                "candidate_id": candidate_id,
                "suggestions": [{
                    **c,
                    "page": 12,
                    "text": "The treaty was signed in 1923. The parties agreed.",
                } for c in cards],
            })
        packs.append({
            "answer_key_accessed": False,
            "teacher_approval": False,
            "runtime_enabled": False,
            "qlora_enabled": False,
            "kaggle_enabled": False,
            "source_checksum": "b" * 64,
            "corpus_checksum": "c" * 64,
            "question_count": len(pack_reviews),
            "reviews": pack_reviews,
        })
        reports.append({
            "answer_key_accessed": False,
            "worked_explanation_accessed": False,
            "teacher_approval": False,
            "runtime_enabled": False,
            "qlora_enabled": False,
            "kaggle_enabled": False,
            "all_new_crops_visually_checked": True,
            "source_checksum": "b" * 64,
            "corpus_checksum": "c" * 64,
            "review_count": len(review_rows),
            "reviews": review_rows,
        })
    return (*packs, *reports, {"source_checksum": "b" * 64, "proposals": proposals})


def test_merges_full_blind_partition_and_audits_quotes():
    result = merge(*fixtures())

    assert result["review_count"] == 89
    assert result["supported_candidate_count"] == 89
    assert result["text_only_supported_candidate_count"] == 89
    assert result["citation_issue_count"] == 0
    assert result["teacher_approval"] is False
    assert result["qlora_enabled"] is False


def test_rejects_answer_key_access_or_incomplete_visual_check():
    packs_a, packs_b, report_a, report_b, queue = fixtures()
    report_b["answer_key_accessed"] = True
    with pytest.raises(ValueError, match="answer_key_accessed"):
        merge(packs_a, packs_b, report_a, report_b, queue)

    report_b["answer_key_accessed"] = False
    report_b["all_new_crops_visually_checked"] = False
    with pytest.raises(ValueError, match="görsel kontrol"):
        merge(packs_a, packs_b, report_a, report_b, queue)

    report_b["all_new_crops_visually_checked"] = True
    report_b["corpus_checksum"] = "d" * 64
    with pytest.raises(ValueError, match="corpus_checksum"):
        merge(packs_a, packs_b, report_a, report_b, queue)


def test_rejects_claimed_support_when_quote_or_source_is_not_verifiable():
    packs_a, packs_b, report_a, report_b, queue = fixtures()
    report_a["reviews"][0]["evidence"][0]["quote"] = "The treaty was signed in 1918."
    with pytest.raises(ValueError, match="provenance/alinti"):
        merge(packs_a, packs_b, report_a, report_b, queue)

    packs_a, packs_b, report_a, report_b, queue = fixtures()
    report_a["reviews"][0]["evidence"][0]["page"] = 11
    with pytest.raises(ValueError, match="provenance/alinti"):
        merge(packs_a, packs_b, report_a, report_b, queue)


def test_rejects_a_question_review_without_visual_inspection_of_every_crop():
    packs_a, packs_b, report_a, report_b, queue = fixtures()
    report_a["reviews"][0]["visually_checked_chunk_ids"] = []
    with pytest.raises(ValueError, match="her yeni PDF kırpımı"):
        merge(packs_a, packs_b, report_a, report_b, queue)


def test_relevant_and_irrelevant_labels_must_partition_every_reviewed_crop():
    packs_a, packs_b, report_a, report_b, queue = fixtures()
    report_a["reviews"][0]["irrelevant_chunk_ids"].pop()

    with pytest.raises(ValueError, match="tüm slate'i çakışmasız"):
        merge(packs_a, packs_b, report_a, report_b, queue)


def test_supported_candidate_is_not_counted_if_visual_dependency_is_found():
    packs_a, packs_b, report_a, report_b, queue = fixtures()
    report_a["reviews"][0]["visual_independence"] = "visual_dependent"

    result = merge(packs_a, packs_b, report_a, report_b, queue)

    assert result["supported_candidate_count"] == 89
    assert result["text_only_supported_candidate_count"] == 88
    assert result["visual_scope_counts"]["visual_dependent"] == 1


def test_insufficient_decision_can_retain_partial_citation_without_supporting_it():
    packs_a, packs_b, report_a, report_b, queue = fixtures()
    row = report_a["reviews"][0]
    row["final_decision"] = "insufficient"
    row["supporting_chunk_ids"] = []
    row["unsupported_claims"] = ["The source omits the requested distinction."]

    result = merge(packs_a, packs_b, report_a, report_b, queue)

    assert result["decision_counts"]["insufficient"] == 1
    assert result["supported_candidate_count"] == 88


def test_multirelation_question_can_cite_up_to_five_distinct_evidence_atoms():
    packs_a, packs_b, report_a, report_b, queue = fixtures(question_count=2)
    pack_row = packs_a["reviews"][0]
    report_row = report_a["reviews"][0]
    cards = pack_row["new_evidence_cards"]
    extra = cards[1]
    report_row["supporting_chunk_ids"].append(extra["chunk_id"])
    report_row["evidence"].append({
        "chunk_id": extra["chunk_id"],
        "source_checksum": extra["source_checksum"],
        "page": extra["source_page"],
        "quote": "The treaty was signed in 1923.",
        "claim_supported": "The question asks when the treaty was signed.",
    })

    result = merge(
        packs_a, packs_b, report_a, report_b, queue,
        expected_question_count=2,
    )

    assert result["citation_issue_count"] == 0


def test_rejects_more_than_five_evidence_atoms():
    packs_a, packs_b, report_a, report_b, queue = fixtures(question_count=2)
    pack_row = packs_a["reviews"][0]
    report_row = report_a["reviews"][0]
    cards = pack_row["new_evidence_cards"]
    for card in cards[1:6]:
        report_row["supporting_chunk_ids"].append(card["chunk_id"])
        report_row["evidence"].append({
            "chunk_id": card["chunk_id"],
            "source_checksum": card["source_checksum"],
            "page": card["source_page"],
            "quote": "The treaty was signed in 1923.",
            "claim_supported": "The question asks when the treaty was signed.",
        })

    with pytest.raises(ValueError, match="en fazla 5 alıntılı kaynak"):
        merge(
            packs_a, packs_b, report_a, report_b, queue,
            expected_question_count=2,
        )


def test_merges_combined_top48_review_with_explicit_scope():
    packs_a, packs_b, report_a, report_b, queue = fixtures(
        question_count=2,
        crops_per_question=48,
    )

    result = merge(
        packs_a,
        packs_b,
        report_a,
        report_b,
        queue,
        expected_question_count=2,
        expected_crops_per_question=48,
        result_schema="dort-dortluk-v9-top48-review-merged-v1",
    )

    assert result["schema"] == "dort-dortluk-v9-top48-review-merged-v1"
    assert result["review_count"] == 2
    assert result["citation_issue_count"] == 0


def test_requires_original_question_page_review_when_source_image_is_in_pack():
    packs_a, packs_b, report_a, report_b, queue = fixtures(
        question_count=2,
        crops_per_question=48,
    )
    queue["source_checksum"] = "b" * 64
    packs_a["question_source_checksum"] = "b" * 64
    report_a["question_source_checksum"] = "b" * 64
    report_a["all_question_source_pages_visually_checked"] = True
    report_a["visually_checked_question_page_count"] = len(packs_a["reviews"])
    report_a["visually_checked_crop_count"] = len(packs_a["reviews"]) * 48
    pack_row = packs_a["reviews"][0]
    pack_row["question_source_page_image"] = "questions/q0.png"
    pack_row["question_source_pdf_page"] = 23
    review_row = report_a["reviews"][0]
    review_row["question_source_pdf_page"] = 23

    with pytest.raises(ValueError, match="orijinal soru sayfası"):
        merge(
            packs_a,
            packs_b,
            report_a,
            report_b,
            queue,
            expected_question_count=2,
            expected_crops_per_question=48,
        )

    report_a["all_question_source_pages_visually_checked"] = True
    review_row["question_source_page_visual_checked"] = True
    review_row["question_source_pdf_page"] = 23
    result = merge(
        packs_a,
        packs_b,
        report_a,
        report_b,
        queue,
        expected_question_count=2,
        expected_crops_per_question=48,
    )

    assert result["review_count"] == 2
