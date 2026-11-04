import pytest

from app.pipeline.ogm_ayt_queue_subset import baseline_abstentions


def _queue():
    return {"schema": "ogm-ayt-manual-source-discovery-v1", "source_checksum": "q",
            "corpus_checksum": "c", "proposals": [
                {"candidate_id": "one", "suggestions": []},
                {"candidate_id": "two", "suggestions": []},
            ]}


def _gold():
    return {"schema": "ogm-ayt-retrieval-gold-v1", "source_checksum": "q", "corpus_checksum": "c",
            "cases": [
                {"candidate_id": "one", "reviewed": True, "coverage_complete": True, "abstain": True},
                {"candidate_id": "two", "reviewed": True, "coverage_complete": True, "abstain": False},
            ]}


def test_subset_keeps_only_complete_baseline_abstentions():
    result = baseline_abstentions(_queue(), _gold())
    assert [row["candidate_id"] for row in result["proposals"]] == ["one"]


def test_subset_rejects_unreviewed_gold():
    gold = _gold()
    gold["cases"][0]["reviewed"] = False
    with pytest.raises(ValueError, match="tam incelenmiş"):
        baseline_abstentions(_queue(), gold)
