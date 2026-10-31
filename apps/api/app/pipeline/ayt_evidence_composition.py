"""Propose review-only two-cut evidence chains; never approve a composed source."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from ..history_rag import STOP, terms


def _plans(plan: dict) -> dict[str, dict]:
    return {row["candidate_id"]: row for row in plan.get("cases", plan.get("plans", []))}


def _claim_ids(item: dict) -> set[str]:
    if item.get("claim_match_status") == "partial_candidate":
        return set()
    return set(item.get("claim_ids") or [item.get("claim_id")]) - {None}


def _bridge_terms(left: dict, right: dict) -> list[str]:
    """Return lexical bridge leads. A reviewer must establish the real edge."""
    shared = set(terms(left["text"])) & set(terms(right["text"]))
    return sorted(term for term in shared if len(term) >= 4 and term not in STOP)[:8]


def build(proposals: dict, plan: dict) -> dict:
    if proposals.get("schema") != "ayt-evidence-bundle-proposals-v1":
        raise ValueError("Beklenen kanıt demeti öneri şeması bulunamadı")
    if plan.get("corpus_checksum") != proposals.get("corpus_checksum"):
        raise ValueError("Kanıt planı ve demet kaynak sürümleri eşleşmiyor")
    plan_by_id = _plans(plan)
    rows = []
    for proposal in proposals.get("proposals", []):
        if proposal["candidate_id"] not in plan_by_id:
            raise ValueError("Demet için kanıt planı bulunamadı")
        required = set(proposal.get("evidence_plan", {}).get("required_claim_ids", []))
        chains = []
        for left, right in itertools.combinations(proposal.get("suggestions", []), 2):
            if left["source_key"] == right["source_key"]:
                continue
            bridge = _bridge_terms(left, right)
            if not bridge:
                continue
            covered = sorted(_claim_ids(left) | _claim_ids(right))
            roles = set(left.get("suggested_roles") or [left.get("suggested_role")])
            roles.update(right.get("suggested_roles") or [right.get("suggested_role")])
            chains.append({
                "card_source_keys": [left["source_key"], right["source_key"]],
                "candidate_bridge_terms": bridge,
                "covered_claim_ids": covered,
                "missing_claim_ids": sorted(required - set(covered)),
                "has_primary_role": "primary" in roles,
                "cross_source": left["source_checksum"] != right["source_checksum"],
                "review_status": "bridge_review_required",
            })
        chains.sort(key=lambda row: (len(row["missing_claim_ids"]), -len(row["candidate_bridge_terms"]), row["card_source_keys"]))
        rows.append({"candidate_id": proposal["candidate_id"],
                     "status": "bridge_review_required" if chains else "no_bridge_candidate",
                     "chains": chains[:8]})
    return {
        "schema": "ayt-evidence-composition-proposals-v1",
        "corpus_checksum": proposals["corpus_checksum"],
        "question_source_checksum": proposals["question_source_checksum"],
        "proposals": rows,
        "notice": "A bridge term is only a private review lead. It is not a graph edge, source approval or student-facing evidence.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.proposals.read_text(encoding="utf-8")), json.loads(args.plan.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
