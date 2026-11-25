import copy
import hashlib
import json

import pytest

from app.pipeline.select_ogm_complete_evidence_review_queue import build


def _inputs():
    queue = {
        "schema": "ogm-ayt-real-question-evidence-queue-v1", "question_source_checksum": "q" * 64,
        "corpus_checksum": "c" * 64, "proposals": [{"candidate_id": "one"}, {"candidate_id": "two"}],
        "runtime_enabled": False,
    }
    digest = hashlib.sha256(json.dumps(queue, sort_keys=True).encode()).hexdigest()
    review = {
        "schema": "deepseek-ogm-ayt-evidence-review-v1", "queue_checksum": digest,
        "question_source_checksum": "q" * 64, "corpus_checksum": "c" * 64,
        "answer_key_accessed": False, "runtime_enabled": False,
        "reviews": [{"candidate_id": "one", "coverage_complete": True}, {"candidate_id": "two", "coverage_complete": False}],
    }
    return queue, review


def test_keeps_only_first_pass_complete_candidates_and_remains_non_runtime():
    queue, review = _inputs()
    result = build(queue, review)
    assert [row["candidate_id"] for row in result["proposals"]] == ["one"]
    assert result["selection"]["requires_second_independent_review"] is True
    assert result["runtime_enabled"] is False


def test_refuses_answer_key_access_or_provenance_mismatch():
    queue, review = _inputs()
    blocked = copy.deepcopy(review)
    blocked["answer_key_accessed"] = True
    with pytest.raises(ValueError, match="cevap anahtarı"):
        build(queue, blocked)
    broken = copy.deepcopy(review)
    broken["queue_checksum"] = "x"
    with pytest.raises(ValueError, match="kaynak zinciri"):
        build(queue, broken)
