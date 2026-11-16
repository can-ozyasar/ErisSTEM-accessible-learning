from __future__ import annotations

import pytest

from app.pipeline.audit_evidence_queue_delta import compare


def card(page: int, *, x: float = 0.0):
    return {"source_checksum": "a" * 64, "page": page, "bbox": [x, 0, 10, 10]}


def queue(strategy: str, cards: list[dict]):
    return {
        "retrieval_strategy": strategy,
        "source_checksum": "b" * 64,
        "corpus_checksum": "c" * 64,
        "proposals": [{
            "candidate_id": "q1",
            "retrieval_ms": 10,
            "suggestions": cards,
        }],
    }


def test_compares_new_candidate_signatures_and_labels_as_diversity_only():
    baseline = queue("claimwise_rrf", [card(1), card(2)])
    candidate = queue("claimwise_option_reserve", [card(2), card(3)])

    result = compare(baseline, candidate)

    assert result["overlap_candidate_count"] == 1
    assert result["unseen_candidate_count"] == 1
    assert result["questions_with_unseen_candidates"] == 1
    assert "doğruluk" in result["interpretation"]


@pytest.mark.parametrize("field", ["source_checksum", "corpus_checksum"])
def test_rejects_different_source_or_corpus_versions(field: str):
    baseline = queue("claimwise_rrf", [card(1)])
    candidate = queue("claimwise_option_reserve", [card(1)])
    candidate[field] = "d" * 64

    with pytest.raises(ValueError):
        compare(baseline, candidate)


def test_rejects_nonmatching_question_sets():
    baseline = queue("claimwise_rrf", [card(1)])
    candidate = queue("claimwise_option_reserve", [card(1)])
    candidate["proposals"][0]["candidate_id"] = "q2"

    with pytest.raises(ValueError):
        compare(baseline, candidate)
