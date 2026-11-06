"""Compare two teacher-agent PDF-crop retrieval audits without answer keys."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

SUPPORT = {"direct", "bounded_inference"}
FAILURES = {"retrieval_miss", "bundle_composition_miss", "target_scope_gap", "none"}


def _rows(payload: dict) -> list[dict]:
    rows = payload.get("records", payload.get("rows", []))
    if not rows:
        raise ValueError("Boş denetim karşılaştırılamaz")
    if payload.get("answer_key_accessed") or payload.get("worked_explanation_accessed"):
        raise ValueError("Cevap veya çözüm erişimli denetim karşılaştırılamaz")
    return rows


def _summary(rows: list[dict]) -> dict:
    assessments = Counter(_assessment(row) for row in rows)
    diagnoses = Counter(row.get("failure_diagnosis") for row in rows)
    return {
        "query_count": len(rows), "support_count": sum(assessments[item] for item in SUPPORT),
        "support_rate": round(sum(assessments[item] for item in SUPPORT) / len(rows), 4),
        "assessment_counts": dict(sorted(assessments.items())), "failure_diagnosis_counts": dict(sorted(diagnoses.items())),
    }


def _assessment(row: dict) -> str | None:
    """Accept the common review field while retaining old audit compatibility."""
    return row.get("decision", row.get("assessment"))


def build(baseline: dict, candidate: dict) -> dict:
    base_rows, candidate_rows = _rows(baseline), _rows(candidate)
    if baseline.get("reviewer_kind") != "history_teacher_agent_v1" or candidate.get("reviewer_kind") != "history_teacher_agent_v1":
        raise ValueError("Ajan öğretmen provenance kaydı zorunlu")
    by_base = {row["candidate_id"]: row for row in base_rows}
    by_candidate = {row["candidate_id"]: row for row in candidate_rows}
    if set(by_base) != set(by_candidate):
        raise ValueError("Aynı soru kümesi üzerinde karşılaştırma gerekli")
    if any(row.get("reviewer_kind") != "history_teacher_agent_v1" for row in candidate_rows):
        raise ValueError("Soru düzeyi ajan provenance kaydı zorunlu")
    base, dense = _summary(base_rows), _summary(candidate_rows)
    changes = Counter()
    transitions = Counter()
    for candidate_id, baseline_row in by_base.items():
        before_label = _assessment(baseline_row)
        after_label = _assessment(by_candidate[candidate_id])
        before = before_label in SUPPORT
        after = after_label in SUPPORT
        transitions[f"{before_label}_to_{after_label}"] += 1
        changes["improved" if not before and after else "regressed" if before and not after else "unchanged"] += 1
    return {
        "schema": "ayt-retrieval-agent-audit-delta-v1", "baseline": base, "candidate": dense,
        "delta": {"support_count": dense["support_count"] - base["support_count"], "support_rate": round(dense["support_rate"] - base["support_rate"], 4), **dict(changes),
                  "quality_transitions": dict(sorted(transitions.items()))},
        "accepted_for_next_review_stage": dense["support_count"] > base["support_count"] and changes["regressed"] == 0,
        "reviewer_kind": "history_teacher_agent_v1", "is_human_teacher_approval": False,
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "A positive retrieval delta prioritizes further crop/bundle review only; it is not a runtime or QLoRA approval.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.baseline), load(args.candidate))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["delta"], ensure_ascii=False))


if __name__ == "__main__":
    main()
