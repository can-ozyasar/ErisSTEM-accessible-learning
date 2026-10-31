"""Content-free coverage metrics for private claim-planned evidence proposals."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

_STATUSES = {"teacher_review_required", "reretrieve_required", "insufficient_evidence"}


def summarize(proposals: dict) -> dict:
    if proposals.get("schema") != "ayt-evidence-bundle-proposals-v1":
        raise ValueError("Beklenen kanıt demeti öneri şeması bulunamadı")
    rows = proposals.get("proposals", [])
    if any(row.get("status") not in _STATUSES for row in rows):
        raise ValueError("Kanıt demeti durumu geçersiz")
    required = sum(len(row.get("evidence_plan", {}).get("required_claim_ids", [])) for row in rows)
    missing = sum(len(row.get("evidence_plan", {}).get("missing_claim_ids", [])) for row in rows)
    complete = sum(row["status"] == "teacher_review_required" for row in rows)
    reretrieve = sum(row["status"] == "reretrieve_required" for row in rows)
    insufficient = sum(row["status"] == "insufficient_evidence" for row in rows)
    suggestions = sum(len(row.get("suggestions", [])) for row in rows)
    discovery = sum(
        item.get("review_status") == "discovery_candidate"
        for row in rows for item in row.get("suggestions", [])
    )
    # Any approved flag would violate this stage of the pipeline.  The source
    # role/crop gate lives in the separate teacher-review artifact.
    approvals = sum(
        item.get("review_status") == "approved"
        for row in rows for item in row.get("suggestions", [])
    )
    return {
        "schema": "ayt-evidence-bundle-coverage-v1",
        "corpus_checksum": proposals["corpus_checksum"],
        "question_source_checksum": proposals["question_source_checksum"],
        "summary": {
            "questions": len(rows), "required_claims": required, "missing_claims": missing,
            "required_claim_coverage": round((required - missing) / required, 4) if required else 0.0,
            "strict_complete_candidate_count": complete,
            "strict_complete_candidate_rate": round(complete / len(rows), 4) if rows else 0.0,
            "reretrieve_required_count": reretrieve, "insufficient_evidence_count": insufficient,
            "review_suggestions": suggestions, "partial_discovery_suggestions": discovery,
            "source_approval_count": approvals,
        },
        "notice": "Coverage is a retrieval diagnostic, never source approval or model-quality evidence.",
    }


def compare(baseline: dict, candidate: dict) -> dict:
    before, after = summarize(baseline), summarize(candidate)
    if (before["corpus_checksum"], before["question_source_checksum"]) != (
        after["corpus_checksum"], after["question_source_checksum"]
    ):
        raise ValueError("Karşılaştırılan demetler aynı kaynak sürümüne bağlı olmalı")
    a, b = before["summary"], after["summary"]
    return {
        "schema": "ayt-evidence-bundle-coverage-comparison-v1",
        "corpus_checksum": before["corpus_checksum"],
        "question_source_checksum": before["question_source_checksum"],
        "baseline": a, "candidate": b,
        "delta": {
            "missing_claims": b["missing_claims"] - a["missing_claims"],
            "required_claim_coverage": round(b["required_claim_coverage"] - a["required_claim_coverage"], 4),
            "strict_complete_candidate_count": b["strict_complete_candidate_count"] - a["strict_complete_candidate_count"],
            "source_approval_count": b["source_approval_count"] - a["source_approval_count"],
        },
        "notice": "A lower missing-claim count is discovery improvement only; crop review remains mandatory.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    single = sub.add_parser("summarize")
    single.add_argument("--proposals", type=Path, required=True)
    single.add_argument("--output", type=Path, required=True)
    paired = sub.add_parser("compare")
    paired.add_argument("--baseline", type=Path, required=True)
    paired.add_argument("--candidate", type=Path, required=True)
    paired.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "summarize":
        result = summarize(json.loads(args.proposals.read_text(encoding="utf-8")))
    else:
        result = compare(json.loads(args.baseline.read_text(encoding="utf-8")),
                         json.loads(args.candidate.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
