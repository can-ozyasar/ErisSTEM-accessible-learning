"""Audit an independent, blind V7 evidence review and reconcile decisions.

This is an offline/private-data audit. It does not approve sources for runtime
or QLoRA; the generated summary keeps those gates closed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PACK = (
    "data/private/ogm-supplementary-v1/"
    "dort-dortluk-evidence-review-v7-independent-blind-audit"
)
DEFAULT_V7_SUMMARY = (
    "data/private/ogm-supplementary-v1/"
    "dort-dortluk-evidence-review-v7-top24-delta/adjudicated-summary.json"
)
DEFAULT_OUTPUT = "adjudicated-summary.json"

# This candidate was conservatively rejected because the cited evidence
# describes Halkçılık but does not establish both principles asked for.
CONSERVATIVE_OVERRIDES = {
    "dort-dortluk:9c94308aec66:p255:q1": {
        "decision": "insufficient",
        "reason": (
            "The reviewed passage supports a connection between Halkçılık and "
            "social solidarity, but it does not establish both principles in "
            "the answer pair. A bounded inference cannot fill in the missing "
            "second relation from model knowledge."
        ),
    }
}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return value


def audit_review(pack_dir: Path, v7_summary_path: Path) -> dict[str, Any]:
    manifest = _read_json(pack_dir / "manifest.json")
    review = _read_json(pack_dir / "independent-review-agent-c-v1.json")
    prior = _read_json(v7_summary_path)

    if manifest.get("schema") != "dort-dortluk-v7-independent-blind-recheck-pack-v1":
        raise ValueError("Unexpected independent review manifest schema")
    if review.get("schema") != "independent_blind_source_review_v1":
        raise ValueError("Unexpected independent review report schema")
    if manifest.get("source_checksum") != review.get("source_checksum"):
        raise ValueError("Question source checksum differs from report")
    if manifest.get("corpus_checksum") != review.get("corpus_checksum"):
        raise ValueError("Evidence corpus checksum differs from report")
    for payload in (manifest, review):
        if any(
            payload.get(flag) is not False
            for flag in (
                "answer_key_accessed",
                "worked_explanation_accessed",
                "teacher_approval",
                "runtime_enabled",
                "qlora_enabled",
            )
        ):
            raise ValueError("A protected review gate is unexpectedly enabled")
    if review.get("all_new_crops_visually_checked") is not True:
        raise ValueError("Reviewer did not attest to visual inspection of all crops")

    manifest_rows = manifest.get("reviews", [])
    report_rows = review.get("reviews", [])
    if len(manifest_rows) != manifest.get("question_count"):
        raise ValueError("Manifest question count does not match its rows")
    if len(report_rows) != len(manifest_rows):
        raise ValueError("Review report does not cover every manifest question")
    manifest_by_id = {row["candidate_id"]: row for row in manifest_rows}
    report_by_id = {row["candidate_id"]: row for row in report_rows}
    if len(manifest_by_id) != len(manifest_rows) or set(manifest_by_id) != set(report_by_id):
        raise ValueError("Candidate IDs are duplicated or do not align")

    checked_crop_count = 0
    citation_count = 0
    for candidate_id, row in report_by_id.items():
        manifest_row = manifest_by_id[candidate_id]
        cards = {card["chunk_id"]: card for card in manifest_row["new_evidence_cards"]}
        checked_ids = row.get("visually_checked_chunk_ids", [])
        if len(checked_ids) != len(cards) or set(checked_ids) != set(cards):
            raise ValueError(f"Visual crop IDs are incomplete for {candidate_id}")
        checked_crop_count += len(checked_ids)
        if row.get("visual_independence") != "text_only":
            raise ValueError(f"Out-of-scope visual question in review: {candidate_id}")
        for citation in row.get("citations", []):
            citation_count += 1
            card = cards.get(citation.get("chunk_id"))
            if card is None:
                raise ValueError(f"Citation is outside its review pack: {candidate_id}")
            if citation.get("source_checksum") != card.get("source_checksum"):
                raise ValueError(f"Citation checksum mismatch: {candidate_id}")
            if citation.get("source_page") != card.get("source_page"):
                raise ValueError(f"Citation page mismatch: {candidate_id}")
            crop_path = pack_dir / card["crop"]
            if not crop_path.is_file():
                raise ValueError(f"Missing cited crop image: {crop_path}")

    prior_by_id = {row["candidate_id"]: row for row in prior["reviews"]}
    if not set(manifest_by_id).issubset(prior_by_id):
        raise ValueError("Independent sample contains a question absent from V7")

    adjudicated_rows: list[dict[str, Any]] = []
    for candidate_id, row in report_by_id.items():
        prior_decision = prior_by_id[candidate_id]["final_decision"]
        override = CONSERVATIVE_OVERRIDES.get(candidate_id)
        decision = override["decision"] if override else row["review_decision"]
        adjudicated_rows.append(
            {
                "candidate_id": candidate_id,
                "prior_v7_decision": prior_decision,
                "independent_agent_decision": row["review_decision"],
                "adjudicated_decision": decision,
                "matches_prior_v7": decision == prior_decision,
                "manual_adjudication_reason": override["reason"] if override else None,
                "teacher_approval": False,
            }
        )

    prior_supported = {
        candidate_id
        for candidate_id in manifest_by_id
        if prior_by_id[candidate_id]["final_decision"]
        in {"direct", "bounded_inference"}
    }
    reproduced_prior_supported = {
        row["candidate_id"]
        for row in adjudicated_rows
        if row["candidate_id"] in prior_supported
        and row["adjudicated_decision"] in {"direct", "bounded_inference"}
    }
    counts = Counter(row["adjudicated_decision"] for row in adjudicated_rows)
    return {
        "schema": "dort-dortluk-v7-independent-review-adjudication-v1",
        "source_checksum": review["source_checksum"],
        "corpus_checksum": review["corpus_checksum"],
        "question_count": len(adjudicated_rows),
        "visually_checked_crop_count": checked_crop_count,
        "citation_count": citation_count,
        "adjudicated_decision_counts": dict(sorted(counts.items())),
        "prior_supported_candidate_count_in_sample": len(prior_supported),
        "prior_supported_candidates_reproduced": len(reproduced_prior_supported),
        "prior_supported_reproduction_rate_in_enriched_sample": (
            len(reproduced_prior_supported) / len(prior_supported)
            if prior_supported
            else None
        ),
        "sampling_note": (
            "The sample intentionally includes all five prior V7 supported "
            "candidates plus five topic-stratified insufficient candidates; "
            "the reproduction rate is not an unbiased corpus-wide precision estimate."
        ),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "teacher_approval": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "kaggle_enabled": False,
        "reviews": adjudicated_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-dir", default=DEFAULT_PACK)
    parser.add_argument("--prior-summary", default=DEFAULT_V7_SUMMARY)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    pack_dir = (REPO_ROOT / args.pack_dir).resolve()
    prior_summary = (REPO_ROOT / args.prior_summary).resolve()
    output = (pack_dir / args.output).resolve()
    result = audit_review(pack_dir, prior_summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "question_count",
        "visually_checked_crop_count",
        "citation_count",
        "adjudicated_decision_counts",
        "prior_supported_candidate_count_in_sample",
        "prior_supported_candidates_reproduced",
        "prior_supported_reproduction_rate_in_enriched_sample",
        "teacher_approval",
        "runtime_enabled",
        "qlora_enabled",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
