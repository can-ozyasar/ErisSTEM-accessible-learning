from app.pipeline.ogm_ayt_relation_review_evaluate import merge_and_evaluate


def _queue():
    return {"schema": "ogm-ayt-relation-discovery-review-queue-v1", "source_checksum": "q", "corpus_checksum": "c",
            "proposals": [{"candidate_id": "one", "suggestions": [
                {"source_checksum": "book", "chunk_id": "a"}, {"source_checksum": "book", "chunk_id": "b"},
            ]}]}


def _rankings():
    rows = {method: ["book:a", "book:b"] for method in (
        "bm25", "bge_dense", "bge_sparse", "rrf", "bge_dense_rerank",
    )}
    return {"schema": "ogm-ayt-relation-retrieval-rankings-v1", "source_checksum": "q", "corpus_checksum": "c",
            "rankings": {"one": rows}}


def _batch():
    return {"schema": "relation-agent-review-v1", "source_checksum": "q", "corpus_checksum": "c",
            "answer_key_accessed": False, "worked_explanation_accessed": False,
            "runtime_enabled": False, "qlora_enabled": False, "reviews": [{
                "candidate_id": "one", "reviewed": True, "crop_checked": True, "coverage_complete": True,
                "reviewer": "agent", "reviewer_kind": "history_teacher_agent_v1", "abstain": False,
                "question_diagnosis": "direct_evidence_found", "judgments": [
                    {"source_key": "book:a", "verdict": "support", "diagnostic": "direct_support"},
                    {"source_key": "book:b", "verdict": "wrong", "diagnostic": "irrelevant"},
                ]}]}


def test_relation_review_evaluation_scores_all_methods_only_after_complete_blind_review():
    result = merge_and_evaluate(_queue(), _rankings(), [_batch()])
    assert result["method_metrics"]["bge_dense"]["recall_at_3"] == 1
    assert result["question_diagnoses"] == {"direct_evidence_found": 1}


def test_relation_review_accepts_a_grounded_multi_atom_bundle():
    batch = _batch()
    review = batch["reviews"][0]
    review["question_diagnosis"] = "multi_atom_required"
    review["judgments"][0]["diagnostic"] = "multi_atom_candidate"
    review["judgments"][1] = {"source_key": "book:b", "verdict": "support", "diagnostic": "multi_atom_candidate"}
    result = merge_and_evaluate(_queue(), _rankings(), [batch])
    assert result["question_diagnoses"] == {"multi_atom_required": 1}


def test_relation_review_uses_the_queue_declared_method_set():
    queue = _queue()
    queue["ranking_methods"] = ["qwen_dense"]
    rankings = _rankings()
    rankings["rankings"]["one"]["qwen_dense"] = ["book:a", "book:b"]
    result = merge_and_evaluate(queue, rankings, [_batch()])
    assert set(result["method_metrics"]) == {"qwen_dense"}


def test_relation_review_uses_only_complete_reported_query_latencies():
    rankings = _rankings()
    rankings["latencies_by_method_ms"] = {method: [12.5] for method in rankings["rankings"]["one"]}
    result = merge_and_evaluate(_queue(), rankings, [_batch()])
    assert result["method_metrics"]["bge_dense"]["p95_ms"] == 12.5
    assert result["latency_status"]["bge_dense"] == "measured_end_to_end"
    rankings["latencies_by_method_ms"]["bge_dense"] = []
    try:
        merge_and_evaluate(_queue(), rankings, [_batch()])
    except ValueError as error:
        assert "gecikme" in str(error)
    else:
        raise AssertionError("Eksik gecikme ölçümü reddedilmeliydi")
