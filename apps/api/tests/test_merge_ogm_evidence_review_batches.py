import copy

import pytest

from app.pipeline.merge_ogm_evidence_review_batches import merge


def _inputs():
    queue = {
        "schema": "ogm-ayt-real-question-evidence-queue-v1",
        "question_source_checksum": "q" * 64,
        "corpus_checksum": "c" * 64,
        "proposals": [{"candidate_id": "q1"}, {"candidate_id": "q2"}],
    }
    import hashlib
    import json
    digest = hashlib.sha256(json.dumps(queue, sort_keys=True).encode()).hexdigest()
    def batch(identifier, complete):
        return {
            "schema": "deepseek-ogm-ayt-evidence-review-v1", "queue_checksum": digest,
            "question_source_checksum": "q" * 64, "corpus_checksum": "c" * 64,
            "model": "deepseek-chat", "answer_key_accessed": False, "runtime_enabled": False,
            "reviews": [{"candidate_id": identifier, "reviewer": "deepseek-chat", "coverage_complete": complete}],
        }
    return queue, batch("q1", True), batch("q2", False)


def test_merges_disjoint_batches_in_queue_order_without_enabling_runtime():
    queue, first, second = _inputs()
    result = merge(queue, [second, first])
    assert [item["candidate_id"] for item in result["reviews"]] == ["q1", "q2"]
    assert result["summary"] == {"review_count": 2, "complete": 1, "abstained": 1, "queue_count": 2, "is_complete_queue": True}
    assert result["answer_key_accessed"] is False
    assert result["runtime_enabled"] is False


def test_refuses_duplicate_or_provenance_broken_batch():
    queue, first, _ = _inputs()
    with pytest.raises(ValueError, match="tekrarlandı"):
        merge(queue, [first, copy.deepcopy(first)])
    broken = copy.deepcopy(first)
    broken["answer_key_accessed"] = True
    with pytest.raises(ValueError, match="cevap anahtarına"):
        merge(queue, [broken])
