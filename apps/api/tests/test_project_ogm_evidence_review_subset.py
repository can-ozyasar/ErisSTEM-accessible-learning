import hashlib
import json

from app.pipeline.project_ogm_evidence_review_subset import build


def test_projects_complete_parent_review_to_the_subset_queue_checksum():
    parent = {"schema": "ogm-ayt-real-question-evidence-queue-v1", "question_source_checksum": "q", "corpus_checksum": "c", "proposals": [{"candidate_id": "a"}, {"candidate_id": "b"}]}
    subset = {"schema": "ogm-ayt-real-question-evidence-queue-v1", "question_source_checksum": "q", "corpus_checksum": "c", "proposals": [{"candidate_id": "b"}]}
    parent_digest = hashlib.sha256(json.dumps(parent, sort_keys=True).encode()).hexdigest()
    review = {"schema": "deepseek-ogm-ayt-evidence-review-v1", "queue_checksum": parent_digest,
              "question_source_checksum": "q", "corpus_checksum": "c", "answer_key_accessed": False, "runtime_enabled": False,
              "reviews": [{"candidate_id": "a", "coverage_complete": False}, {"candidate_id": "b", "coverage_complete": True}]}
    result = build(parent, subset, review)
    assert [row["candidate_id"] for row in result["reviews"]] == ["b"]
    assert result["summary"]["complete"] == 1
    assert result["queue_checksum"] == hashlib.sha256(json.dumps(subset, sort_keys=True).encode()).hexdigest()
    assert result["runtime_enabled"] is False
