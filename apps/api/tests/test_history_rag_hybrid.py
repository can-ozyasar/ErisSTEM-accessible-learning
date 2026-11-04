import importlib.util
from pathlib import Path

import pytest

from app.history_rag_hybrid import (
    acceptance_decision,
    approval_checksum,
    evaluate_rankings,
    rrf_fuse,
    validate_artifact,
)


def test_rrf_is_deterministic_and_deduplicates_each_ranker():
    one = rrf_fuse({"dense": ["b", "a", "a"], "bm25": ["a", "c"]})
    two = rrf_fuse({"bm25": ["a", "c"], "dense": ["b", "a", "a"]})
    assert one == two
    assert [item["id"] for item in one] == ["a", "b", "c"]


def test_evaluation_rejects_answer_keys_and_scores_abstention():
    queries = [{"id": "q1", "gold_source_ids": ["e1"]}, {"id": "q2", "abstain": True}]
    result = evaluate_rankings(queries, {"q1": ["e1"], "q2": []}, [2, 4])
    assert result["recall_at_3"] == 1
    assert result["hit_at_3"] == 1
    assert result["correct_abstention"] == 1
    with pytest.raises(ValueError):
        evaluate_rankings([{**queries[0], "answer_label": "A"}], {}, [])


def test_multi_source_recall_and_unjudged_candidates_are_distinct():
    result = evaluate_rankings([{"id": "q", "gold_source_ids": ["a", "b"],
                                 "wrong_source_ids": ["c"]}],
                               {"q": ["a", "c", "unknown"]}, [3])
    assert result["hit_at_3"] == 1
    assert result["recall_at_3"] == 0.5
    assert result["evidence_coverage_at_3"] == 0
    assert result["wrong_evidence_rate"] == 0.5
    assert result["wrong_evidence_count"] == 1
    assert result["unjudged_result_count"] == 1


def test_artifact_requires_matching_source_and_approval_versions():
    source = "source-v1"
    approved = {"one", "two"}
    base = evaluate_rankings([{"id": "q", "gold_source_ids": ["one"],
                               "wrong_source_ids": ["two"]}], {"q": ["two"]}, [100])
    candidate = evaluate_rankings([{"id": "q", "gold_source_ids": ["one"],
                                    "wrong_source_ids": ["two"]}], {"q": ["one"]}, [90])
    decision = acceptance_decision(base, candidate, reviewer="Teacher")
    artifact = {"schema": "history-rag-hybrid-v2", "source_checksum": source,
                "approval_checksum": approval_checksum(source, approved), "accepted": True,
                "baseline_metrics": base, "metrics": candidate, "reviewed_by": "Teacher",
                "decision_reason": "Kaynak hatası azaldı, PDF kesitleri incelendi.",
                "delta_vs_bm25": decision["delta_vs_bm25"]}
    assert validate_artifact(artifact, source, approved) == artifact
    with pytest.raises(ValueError):
        validate_artifact(artifact, source, {"one"})
    with pytest.raises(ValueError):
        validate_artifact({**artifact, "schema": "history-rag-hybrid-v1"}, source, approved)


def test_small_latency_gain_can_be_reviewed_if_evidence_is_stable():
    labels = [{"id": "q", "gold_source_ids": ["e"]}]
    base = evaluate_rankings(labels, {"q": ["e"]}, [100])
    candidate = evaluate_rankings(labels, {"q": ["e"]}, [90])
    assert acceptance_decision(base, candidate)["eligible_for_review"]
    assert not acceptance_decision(base, candidate)["accepted"]
    assert acceptance_decision(base, candidate, reviewer="Öğretmen")["accepted"]
    assert not acceptance_decision(base, {**candidate, "p95_ms": 110}, reviewer="Öğretmen")["accepted"]


def test_candidate_cannot_trade_abstention_safety_for_recall():
    labels = [{"id": "answerable", "gold_source_ids": ["e"], "wrong_source_ids": ["w"]},
              {"id": "unanswerable", "abstain": True}]
    base = evaluate_rankings(labels, {"answerable": ["w"], "unanswerable": []}, [100, 100])
    candidate = evaluate_rankings(labels, {"answerable": ["e"], "unanswerable": ["w"]}, [80, 80])
    assert not acceptance_decision(base, candidate, reviewer="Öğretmen")["accepted"]


def test_kaggle_scorer_matches_local_metric_contract():
    script = Path(__file__).parents[3] / "experiments/kaggle/history_rag_hybrid_score.py"
    spec = importlib.util.spec_from_file_location("history_rag_hybrid_score", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    labels = [{"id": "q", "gold_source_ids": ["a", "b"], "wrong_source_ids": ["c"]},
              {"id": "abstain", "abstain": True}]
    rankings = {"q": ["a", "c", "unknown"], "abstain": []}
    assert module.score(labels, rankings, [3, 7]) == evaluate_rankings(labels, rankings, [3, 7])
