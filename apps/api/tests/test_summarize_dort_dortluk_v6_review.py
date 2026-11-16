from __future__ import annotations

import pytest

from app.pipeline.summarize_dort_dortluk_v6_review import summarize


def report(rows, *, side="a", version=6):
    result = {
        "answer_key_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "review_count": len(rows),
        "reviews": [],
    }
    for candidate_id, decision, topic in rows:
        row = {"candidate_id": candidate_id, "topic": topic}
        if version == 4 and side == "a":
            row["question_decision"] = decision
        elif version == 6 and side == "a":
            row["final_decision"] = decision
        else:
            row["bundle_assessment"] = {"decision": decision}
        result["reviews"].append(row)
    return result


def test_merges_split_reports_and_counts_supported_change():
    ids_a = [(f"a{i}", "insufficient", "Ünite A") for i in range(64)]
    ids_b = [(f"b{i}", "direct", "Ünite B") for i in range(64)]
    v4a = report(ids_a, version=4)
    v4b = report(ids_b, side="b", version=4)
    v6a = report([( "a0", "bounded_inference", "Ünite A"), *ids_a[1:]])
    v6b = report(ids_b, side="b")

    result = summarize(v4a, v4b, v6a, v6b)

    assert result["review_count"] == 128
    assert result["supported_bundle_count"] == 65
    assert result["supported_bundle_delta"] == 1
    assert result["changed_decisions"] == [
        {"candidate_id": "a0", "from": "insufficient", "to": "bounded_inference"}
    ]
    assert result["qlora_enabled"] is False


def test_rejects_incomplete_or_overlapping_review_partitions():
    ids_a = [(f"a{i}", "insufficient", "Ünite A") for i in range(64)]
    ids_b = [(f"b{i}", "direct", "Ünite B") for i in range(64)]
    v4a = report(ids_a, version=4)
    v4b = report(ids_b, side="b", version=4)
    v6a = report(ids_a)
    v6b = report(ids_a, side="b")

    with pytest.raises(ValueError, match="tam bir kez"):
        summarize(v4a, v4b, v6a, v6b)


def test_rejects_answer_key_access():
    v4a = report([], version=4)
    v4b = report([], side="b", version=4)
    v6a = report([], version=6)
    v6b = report([], side="b", version=6)
    v6b["answer_key_accessed"] = True

    with pytest.raises(ValueError, match="cevap anahtarı"):
        summarize(v4a, v4b, v6a, v6b)


def test_applies_question_integrity_adjudication_before_counting():
    ids_a = [(f"a{i}", "direct", "Ünite A") for i in range(64)]
    ids_b = [(f"b{i}", "insufficient", "Ünite B") for i in range(64)]
    reports = (
        report(ids_a, version=4), report(ids_b, side="b", version=4),
        report(ids_a), report(ids_b, side="b"),
    )
    result = summarize(*reports, adjudications={
        "answer_key_accessed": False,
        "teacher_approval": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "adjudications": [{
            "candidate_id": "a0", "decision": "insufficient",
            "question_integrity": "ambiguous_or_inconsistent_question_stem",
            "reason": "Soru kökü ile kaynaklar tüm iddialarda uyuşmuyor.",
        }],
    })

    assert result["supported_bundle_count"] == 63
    assert result["v6_decision_counts"]["insufficient"] == 65
    assert result["adjudications_applied"][0]["from"] == "direct"
