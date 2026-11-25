"""Promote only exact final evidence bundles that pass local AI/PDF gates.

This is an AI-reviewed local-pilot gate, never a human-teacher approval or
publication decision. Incomplete/contested evidence remains unavailable to
the student coach while the question itself remains usable in the exam.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

from .audit_exam_pack_evidence_pdf import audit as audit_pdf_evidence

PACK_SCHEMA = "ayt-history-exam-pack-v1"
QUEUE_SCHEMA = "ogm-ayt-real-question-evidence-queue-v1"
REVIEW_SCHEMA = "deepseek-ogm-ayt-evidence-review-v1"
ANSWER_SCHEMA = "ogm-final-bundle-answer-review-v1"


def _queue_checksum(queue: dict[str, Any]) -> str:
    # Match the checksum used by the existing DeepSeek review pipeline.
    return hashlib.sha256(json.dumps(queue, sort_keys=True).encode()).hexdigest()


def _pack_checksum(pack: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        pack, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()


def _latency_summary(review: dict[str, Any]) -> dict[str, float | int | None]:
    values = sorted(row["latency_ms"] for row in review.get("reviews", [])
                    if isinstance(row.get("latency_ms"), (int, float)) and row["latency_ms"] >= 0)
    if not values:
        return {"count": 0, "p50_ms": None, "p95_ms": None}
    return {"count": len(values), "p50_ms": round(median(values), 2),
            "p95_ms": round(values[math.ceil(0.95 * len(values)) - 1], 2)}


def _git_commit() -> str | None:
    repository = Path(__file__).resolve().parents[4]
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _coverage_complete(row: dict[str, Any], allowed_ids: set[str]) -> bool:
    support = row.get("support_ids")
    return (row.get("coverage_complete") is True and row.get("abstain") is False
            and isinstance(support, list) and len(support) > 0
            and len(set(support)) == len(support) and set(support) <= allowed_ids)


def _review_map(review: dict[str, Any], expected_ids: set[str], queue: dict[str, Any], *,
                label: str) -> dict[str, dict[str, Any]]:
    if (review.get("schema") != REVIEW_SCHEMA
            or review.get("queue_checksum") != _queue_checksum(queue)
            or review.get("question_source_checksum") != queue.get("question_source_checksum")
            or review.get("corpus_checksum") != queue.get("corpus_checksum")
            or review.get("answer_key_accessed") is not False
            or review.get("runtime_enabled") is not False
            or review.get("is_human_teacher_approval") is not False):
        raise ValueError(f"{label}_review_provenance_mismatch")
    rows = review.get("reviews")
    if not isinstance(rows, list):
        raise TypeError(f"{label}_reviews_missing")
    mapped = {row.get("candidate_id"): row for row in rows}
    if len(mapped) != len(rows) or set(mapped) != expected_ids:
        raise ValueError(f"{label}_review_coverage_mismatch")
    return mapped


def _answer_map(batches: list[dict[str, Any]], expected_ids: set[str], queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    queue_checksum = _queue_checksum(queue)
    merged: dict[str, dict[str, Any]] = {}
    for batch in batches:
        if (batch.get("schema") != ANSWER_SCHEMA
                or batch.get("queue_checksum") != queue_checksum
                or batch.get("question_source_checksum") != queue.get("question_source_checksum")
                or batch.get("model_received_answer_key") is not False
                or batch.get("answer_key_compared_locally") is not True
                or batch.get("runtime_enabled") is not False
                or batch.get("is_human_teacher_approval") is not False):
            raise ValueError("answer_review_provenance_mismatch")
        rows = batch.get("reviews")
        if not isinstance(rows, list):
            raise TypeError("answer_review_rows_missing")
        for row in rows:
            identifier = row.get("candidate_id")
            if identifier not in expected_ids or identifier in merged:
                raise ValueError("answer_review_duplicate_or_unexpected_id")
            merged[identifier] = row
    if set(merged) != expected_ids:
        raise ValueError("answer_review_coverage_mismatch")
    return merged


def promote(pack: dict[str, Any], queue: dict[str, Any], first_review: dict[str, Any],
            second_review: dict[str, Any], answer_batches: list[dict[str, Any]],
            pdf_audit: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Copy pack and enable only exact, repeated full-coverage evidence bundles."""
    if (pack.get("schema") != PACK_SCHEMA
            or pack.get("content_mode") != "ai_source_reviewed_local_pilot"
            or pack.get("student_publication_allowed") is not False):
        raise ValueError("non_public_ai_reviewed_pilot_pack_required")
    if (queue.get("schema") != QUEUE_SCHEMA or queue.get("runtime_enabled") is not False
            or queue.get("answer_key_accessed") is not False
            or queue.get("question_source_checksum") != pack.get("licensed_question_source_checksum")):
        raise ValueError("exact_answer_blind_final_bundle_queue_required")

    proposals = queue.get("proposals")
    if not isinstance(proposals, list) or not proposals:
        raise ValueError("final_bundle_queue_empty")
    candidate_ids = [row.get("candidate_id") for row in proposals]
    if any(not isinstance(item, str) or not item for item in candidate_ids) or len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("final_bundle_candidate_ids_invalid")
    expected_ids = set(candidate_ids)
    first = _review_map(first_review, expected_ids, queue, label="first_pass")
    second = _review_map(second_review, expected_ids, queue, label="second_pass")
    answers = _answer_map(answer_batches, expected_ids, queue)

    if pdf_audit.get("schema") != "exam-pack-evidence-pdf-audit-v1" or pdf_audit.get("pack_sha256") != _pack_checksum(pack):
        raise ValueError("pdf_audit_does_not_match_exact_pack_revision")
    pdf_rows: dict[str, list[dict[str, Any]]] = {}
    for row in pdf_audit.get("evidence", []):
        pdf_rows.setdefault(row.get("question_id"), []).append(row)

    updated = json.loads(json.dumps(pack, ensure_ascii=False))
    question_by_id = {row["id"]: row for row in updated["questions"]}
    source_by_id = {row["id"]: row for row in updated["sources"]}
    candidate_to_pack_id = {
        candidate_id: "ai-reviewed-" + hashlib.sha256(candidate_id.encode()).hexdigest()[:20]
        for candidate_id in candidate_ids
    }
    if len(set(candidate_to_pack_id.values())) != len(candidate_ids):
        raise ValueError("candidate_to_pack_id_collision")

    promoted: list[str] = []
    withheld: Counter[str] = Counter()
    allowed_support_ids = {
        row["candidate_id"]: {item["id"] for item in row["suggestions"]}
        for row in proposals
    }
    for proposal in proposals:
        candidate_id = proposal["candidate_id"]
        pack_id = candidate_to_pack_id[candidate_id]
        question = question_by_id.get(pack_id)
        if question is None or question.get("authorship") != "ai_source_reviewed_local_pilot":
            raise ValueError("final_bundle_candidate_not_in_exact_active_pack")

        suggestions = proposal.get("suggestions")
        if not isinstance(suggestions, list) or not 1 <= len(suggestions) <= 3:
            raise ValueError("final_bundle_size_invalid")
        suggestion_by_id = {item.get("id"): item for item in suggestions}
        if len(suggestion_by_id) != len(suggestions) or None in suggestion_by_id:
            raise ValueError("final_bundle_suggestion_ids_invalid")

        def pack_item_matches(item: dict[str, Any], suggestion: dict[str, Any]) -> bool:
            source = source_by_id.get(suggestion.get("source_name"))
            return (source is not None
                    and source.get("source_checksum") == suggestion.get("source_checksum")
                    and item.get("source_id") == suggestion.get("source_name")
                    and item.get("source_checksum") == suggestion.get("source_checksum")
                    and item.get("source_kind") == source.get("kind")
                    and item.get("page") == suggestion.get("page")
                    and item.get("bbox") == suggestion.get("bbox")
                    and item.get("quote") == suggestion.get("excerpt"))

        pack_evidence = question.get("evidence", [])
        if len(pack_evidence) != len(suggestions) or any(
                not any(pack_item_matches(item, suggestion) for item in pack_evidence)
                for suggestion in suggestions):
            raise ValueError("final_bundle_is_not_exact_active_pack_evidence")

        first_row, second_row, answer_row = first[candidate_id], second[candidate_id], answers[candidate_id]
        first_complete = _coverage_complete(first_row, set(suggestion_by_id))
        second_complete = _coverage_complete(second_row, set(suggestion_by_id))
        agreed_support = (first_complete and second_complete
                          and set(first_row["support_ids"]) == set(second_row["support_ids"]))
        answer_matches = (answer_row.get("matches_answer_key") is True
                          and answer_row.get("resolved_label") in {"A", "B", "C", "D", "E"})
        evidence_rows = pdf_rows.get(pack_id, [])
        pdf_ok = (len(evidence_rows) == len(pack_evidence)
                  and all(row.get("requires_review") is False
                          and isinstance(row.get("token_recall"), (int, float))
                          and row["token_recall"] >= pdf_audit.get("threshold", 1.0)
                          for row in evidence_rows))

        # The coach sees only fragments both answer-blind reviews independently
        # selected. Unselected context is not smuggled into the final bundle.
        if agreed_support and answer_matches and pdf_ok:
            support_ids = list(first_row["support_ids"])
            question["evidence"] = [
                {**suggestion, "role": "primary" if index == 0 else "context"}
                for index, support_id in enumerate(support_ids)
                for suggestion in [suggestion_by_id[support_id]]
            ]
            # Runtime evidence schema uses source_id/quote, not queue names.
            question["evidence"] = [{
                "source_id": item["source_name"],
                "source_checksum": item["source_checksum"],
                "source_kind": source_by_id[item["source_name"]]["kind"],
                "page": item["page"], "bbox": item["bbox"],
                "quote": item["excerpt"], "role": item["role"],
            } for item in question["evidence"]]
            question["final_bundle_verified"] = True
            promoted.append(pack_id)
        else:
            question["final_bundle_verified"] = False
            if not first_complete or not second_complete:
                withheld["coverage_incomplete_or_abstained"] += 1
            elif not agreed_support:
                withheld["support_set_disagreement"] += 1
            if not answer_matches:
                withheld["answer_key_mismatch_or_abstention"] += 1
            if not pdf_ok:
                withheld["pdf_quote_or_locator_mismatch"] += 1

    if len([row for row in updated["questions"] if row.get("authorship") == "ai_source_reviewed_local_pilot"]) != len(proposals):
        raise ValueError("active_pack_ai_review_question_count_mismatch")
    if pdf_audit.get("requires_review_count", 1) != 0:
        # Even if this affects only a non-AI question, an evidence audit tied to
        # the active pack must be clean before its AI bundles are promoted.
        raise ValueError("active_pack_pdf_evidence_audit_has_review_items")

    report = {
        "schema": "ogm-ai-final-bundle-promotion-audit-v1",
        "evaluated_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "review_models": {
            "first_pass": first_review.get("model"),
            "second_pass": second_review.get("model"),
            "answer_blind_solver": "deepseek-chat",
            "provider_revision_pinned": False,
        },
        "review_latency_ms": {
            "first_pass": _latency_summary(first_review),
            "second_pass": _latency_summary(second_review),
        },
        "parent_pack_sha256": _pack_checksum(pack),
        "output_pack_sha256": _pack_checksum(updated),
        "question_source_checksum": pack["licensed_question_source_checksum"],
        "meb_corpus_checksum": queue.get("corpus_checksum"),
        "final_bundle_queue_checksum": _queue_checksum(queue),
        "candidate_question_count": len(candidate_ids),
        "first_pass_complete_count": sum(
            _coverage_complete(first[cid], allowed_support_ids[cid]) for cid in candidate_ids),
        "second_pass_complete_count": sum(
            _coverage_complete(second[cid], allowed_support_ids[cid]) for cid in candidate_ids),
        "answer_key_blind_answer_match_count": sum(
            answers[cid].get("matches_answer_key") is True for cid in candidate_ids),
        "support_set_agreement_count": sum(
            _coverage_complete(first[cid], allowed_support_ids[cid])
            and _coverage_complete(second[cid], allowed_support_ids[cid])
            and set(first[cid]["support_ids"]) == set(second[cid]["support_ids"])
            for cid in candidate_ids),
        "pdf_evidence_count": pdf_audit["evidence_count"],
        "pdf_evidence_requires_review_count": pdf_audit["requires_review_count"],
        "promoted_for_source_grounded_coaching": len(promoted),
        "safe_abstention_count": len(candidate_ids) - len(promoted),
        "withheld_reasons": dict(sorted(withheld.items())),
        "promoted_question_ids": promoted,
        "human_teacher_approval": False,
        "student_publication_allowed": False,
        "runtime_enabled": False,
        "notice": "AI/PDF consistency gate only; not human teacher approval, publication permission, or a claim of historical correctness.",
    }
    return updated, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--first-review", type=Path, required=True)
    parser.add_argument("--second-review", type=Path, required=True)
    parser.add_argument("--answer-review", type=Path, action="append", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-pack", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.output_pack.exists() or args.report.exists():
        raise FileExistsError("refusing_to_overwrite_final_bundle_promotion_output")
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    pack = load(args.pack)
    pdf_audit = audit_pdf_evidence(pack, args.source_root)
    updated, report = promote(pack, load(args.queue), load(args.first_review), load(args.second_review),
                              [load(path) for path in args.answer_review], pdf_audit)
    args.output_pack.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output_pack.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "candidate_question_count", "promoted_for_source_grounded_coaching",
        "safe_abstention_count", "pdf_evidence_requires_review_count",
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
