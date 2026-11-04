import pytest

from app.pipeline.ogm_ayt_retrieval_gold import build_template, evaluate


def _queue():
    return {"schema": "ogm-ayt-evidence-review-queue-v3", "source_checksum": "q",
            "corpus_checksum": "c", "proposals": [
                {"candidate_id": "one", "retrieval_ms": 7, "suggestions": [
                    {"source_checksum": "s", "chunk_id": "a"},
                    {"source_checksum": "s", "chunk_id": "b"}]},
            ]}


def _corpus():
    return {"corpus_checksum": "c", "books": [{"source_checksum": "s", "index": {"chunks": [
        {"id": "a"}, {"id": "b"},
    ]}}]}


def test_pending_labels_never_claim_retrieval_accuracy():
    gold = build_template(_queue())
    result = evaluate(_queue(), gold, _corpus())
    assert result["reviewed_count"] == 0
    assert result["metrics"] is None
    assert gold["cases"][0]["coverage_complete"] is False


def test_complete_history_teacher_agent_labels_score_both_correct_and_wrong_sources():
    gold = build_template(_queue())
    case = gold["cases"][0]
    case.update(reviewed=True, crop_checked=True, coverage_complete=True,
                reviewer="Tarih öğretmeni ajanı", reviewer_kind="history_teacher_agent_v1", abstain=False)
    case["judgments"][0]["verdict"] = "support"
    case["judgments"][1]["verdict"] = "wrong"
    result = evaluate(_queue(), gold, _corpus())
    assert result["metrics"]["recall_at_3"] == 1
    assert result["metrics"]["wrong_evidence_rate"] == 0.5
    assert result["metrics"]["unjudged_result_count"] == 0
    assert result["approval_provenance"]["reviewer_kinds"] == ["history_teacher_agent_v1"]
    case["reviewer_kind"] = "unknown_agent"
    with pytest.raises(ValueError, match="inceleyen"):
        evaluate(_queue(), gold, _corpus())
    case["reviewer_kind"] = "history_teacher_agent_v1"
    with pytest.raises(ValueError, match="kaynak sürümü"):
        evaluate({**_queue(), "corpus_checksum": "changed"}, gold, _corpus())


def test_manual_discovery_queue_uses_the_same_private_gold_contract():
    queue = {**_queue(), "schema": "ogm-ayt-manual-source-discovery-v1"}
    gold = build_template(queue)
    assert gold["cases"][0]["candidate_id"] == "one"
