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
    if item.get("claim_match_status") == "partial_candidate" or item.get("claim_proof_mode") != "literal":
        return set()
    return set(item.get("claim_ids") or [item.get("claim_id")]) - {None}


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def _plan_endpoints(case: dict) -> set[str]:
    values = []
    for claim in case.get("evidence_claims", case.get("claims", [])):
        for key in ("entities", "all_of", "all_of_groups", "any_of", "any_of_groups"):
            values.extend(_strings(claim.get(key, [])))
    return set(terms(" ".join(values)))


def _bridge_type(case: dict) -> str | None:
    types = {claim.get("claim_type") for claim in case.get("evidence_claims", case.get("claims", []))}
    if "place_event" in types:
        return "place_event"
    if "date_event" in types or "chronology" in types:
        return "explicit_chronology"
    if "cause_effect" in types:
        return "explicit_causal_link"
    if "person_event" in types:
        return "same_entity"
    return None


def _bridge_terms(left: dict, right: dict, endpoints: set[str]) -> list[str]:
    """Keep only typed, plan-declared literal endpoint pairs as bridge leads."""
    shared = set(terms(left["text"])) & set(terms(right["text"]))
    return sorted(term for term in shared & endpoints if len(term) >= 4 and term not in STOP)


def build(proposals: dict, plan: dict) -> dict:
    if proposals.get("schema") != "ayt-evidence-bundle-proposals-v1":
        raise ValueError("Beklenen kanıt demeti öneri şeması bulunamadı")
    if plan.get("corpus_checksum") != proposals.get("corpus_checksum"):
        raise ValueError("Kanıt planı ve demet kaynak sürümleri eşleşmiyor")
    plan_by_id = _plans(plan)
    rows = []
    for proposal in proposals.get("proposals", []):
        case = plan_by_id.get(proposal["candidate_id"])
        if case is None:
            raise ValueError("Demet için kanıt planı bulunamadı")
        required = set(proposal.get("evidence_plan", {}).get("required_claim_ids", []))
        endpoints, bridge_type = _plan_endpoints(case), _bridge_type(case)
        chains = []
        for left, right in itertools.combinations(proposal.get("suggestions", []), 2):
            if left["source_key"] == right["source_key"]:
                continue
            bridge = _bridge_terms(left, right, endpoints)
            if len(bridge) < 2 or bridge_type is None:
                continue
            covered = sorted(_claim_ids(left) | _claim_ids(right))
            roles = set(left.get("suggested_roles") or [left.get("suggested_role")])
            roles.update(right.get("suggested_roles") or [right.get("suggested_role")])
            chains.append({
                "card_source_keys": [left["source_key"], right["source_key"]],
                "candidate_bridge_terms": bridge,
                "bridge_type": bridge_type,
                "normalized_endpoint_ids": bridge,
                "covered_claim_ids": covered,
                "missing_claim_ids": sorted(required - set(covered)),
                "has_primary_role": "primary" in roles,
                "cross_source": left["source_checksum"] != right["source_checksum"],
                "review_status": "bridge_review_required",
            })
        chains.sort(key=lambda row: (len(row["missing_claim_ids"]), -len(row["candidate_bridge_terms"]), row["card_source_keys"]))
        complete = any(not chain["missing_claim_ids"] and chain["has_primary_role"] for chain in chains)
        rows.append({"candidate_id": proposal["candidate_id"],
                     "status": "bridge_review_required" if complete else (
                         "bridge_review_required_with_identity_reretrieve" if chains else "no_bridge_candidate"
                     ),
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
