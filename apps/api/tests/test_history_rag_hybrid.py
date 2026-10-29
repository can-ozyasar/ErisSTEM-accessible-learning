import pytest

from app.history_rag_hybrid import acceptance_decision, approval_checksum, evaluate_rankings, rrf_fuse, validate_artifact


def test_rrf_is_deterministic_and_deduplicates_each_ranker():
    one = rrf_fuse({"dense": ["b", "a", "a"], "bm25": ["a", "c"]})
    two = rrf_fuse({"bm25": ["a", "c"], "dense": ["b", "a", "a"]})
    assert one == two
    assert [item["id"] for item in one] == ["a", "b", "c"]


def test_evaluation_rejects_answer_keys_and_scores_abstention():
    queries = [{"id": "q1", "gold_source_ids": ["e1"]}, {"id": "q2", "abstain": True}]
    result = evaluate_rankings(queries, {"q1": ["e1"], "q2": []}, [2, 4])
    assert result["recall_at_3"] == 1
    assert result["correct_abstention"] == 1
    with pytest.raises(ValueError):
        evaluate_rankings([{**queries[0], "answer_label": "A"}], {}, [])


def test_artifact_requires_matching_source_and_approval_versions():
    source = "source-v1"
    approved = {"one", "two"}
    artifact = {"schema": "history-rag-hybrid-v1", "source_checksum": source,
                "approval_checksum": approval_checksum(source, approved), "accepted": True,
                "metrics": {"p95_ms": 500},
                "delta_vs_bm25": {"recall_at_3": .05, "mrr_at_3": .03, "wrong_evidence_rate": 0}}
    assert validate_artifact(artifact, source, approved) == artifact
    with pytest.raises(ValueError):
        validate_artifact(artifact, source, {"one"})


def test_acceptance_needs_all_quality_and_latency_gates():
    base = {"recall_at_3": .4, "mrr_at_3": .3, "wrong_evidence_rate": .1}
    candidate = {"recall_at_3": .45, "mrr_at_3": .33, "wrong_evidence_rate": .1, "p95_ms": 1000}
    assert acceptance_decision(base, candidate)["accepted"]
    assert not acceptance_decision(base, {**candidate, "p95_ms": 1001})["accepted"]
