from __future__ import annotations

from app.pipeline.prepare_dort_dortluk_v7_top24_delta import (
    _balanced_partition,
    crop_signature,
    select_unseen_cards,
)


def card(chunk_id: str, page: int, *, bbox=None):
    return {
        "chunk_id": chunk_id,
        "source_checksum": "a" * 64,
        "page": page,
        "bbox": bbox or [1, 2, 30, 40],
    }


def test_crop_signature_uses_source_page_and_rounded_geometry():
    a = card("old-id", 4, bbox=[1.001, 2, 30, 40])
    b = card("new-id", 4, bbox=[1.004, 2, 30, 40])
    assert crop_signature(a) == crop_signature(b)
    assert crop_signature(a) != crop_signature(card("other-page", 5))


def test_selects_only_new_crops_for_unresolved_non_excluded_questions():
    old = card("old-chunk", 4)
    new = card("new-chunk", 8)
    v6 = {"proposals": [{"candidate_id": "q1", "suggestions": [old]}]}
    v7 = {"proposals": [
        {"candidate_id": "q1", "suggestions": [old, new]},
        {"candidate_id": "q2", "suggestions": [new]},
        {"candidate_id": "q3", "suggestions": [new]},
    ]}
    adjudications = {"adjudications": [{"candidate_id": "q2", "decision": "direct"}]}

    selected = select_unseen_cards(v6, v7, adjudications, {"q3"})

    assert list(selected) == ["q1"]
    assert selected["q1"] == [{**new, "_expanded_rank": 2}]


def test_can_reconsider_previous_top12_crops_in_combined_top24_review():
    old = card("old-chunk", 4)
    new = card("new-chunk", 8)
    v6 = {"proposals": [{"candidate_id": "q1", "suggestions": [old]}]}
    v7 = {"proposals": [{"candidate_id": "q1", "suggestions": [old, new]}]}

    selected = select_unseen_cards(
        v6, v7, {"adjudications": []}, set(), include_previous=True)

    assert selected["q1"] == [
        {**old, "_expanded_rank": 1},
        {**new, "_expanded_rank": 2},
    ]


def test_delta_review_deduplicates_atom_and_context_views_of_same_pdf_crop():
    old = card("old", 4)
    atom_view = card("atom-view", 8)
    context_view = card("context-view", 8)
    v6 = {"proposals": [{"candidate_id": "q1", "suggestions": [old]}]}
    v7 = {"proposals": [{"candidate_id": "q1", "suggestions": [
        atom_view, context_view,
    ]}]}

    selected = select_unseen_cards(v6, v7, {"adjudications": []}, set())

    assert selected["q1"] == [{**atom_view, "_expanded_rank": 1}]


def test_atom_candidate_metadata_is_available_for_review_cards():
    atom = card("atom", 8)
    atom.update({"index_layer": "evidence_atom", "extraction_method": "standalone_fact"})
    selected = select_unseen_cards(
        {"proposals": []}, {"proposals": [{"candidate_id": "q1", "suggestions": [atom]}]},
        {"adjudications": []}, set())

    assert selected["q1"][0]["index_layer"] == "evidence_atom"
    assert selected["q1"][0]["extraction_method"] == "standalone_fact"


def test_balanced_partition_keeps_each_question_intact_and_topic_balanced():
    rows = [
        {"candidate_id": f"q{i}", "topic": "Ünite A"}
        for i in range(4)
    ] + [
        {"candidate_id": f"r{i}", "topic": "Ünite B"}
        for i in range(3)
    ]

    a, b = _balanced_partition(rows)

    assert {row["candidate_id"] for row in a} == {"q0", "q2", "r0", "r2"}
    assert {row["candidate_id"] for row in b} == {"q1", "q3", "r1"}
    assert not ({row["candidate_id"] for row in a}
                & {row["candidate_id"] for row in b})
