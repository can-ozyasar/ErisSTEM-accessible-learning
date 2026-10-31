"""Prepare source-bound, review-only graph candidates for the AYT pilot.

The extractor converts only literal claim matches into graph *proposals*.
It never creates an approved graph edge, changes retrieval, or exports data
for QLoRA.  A teacher still checks the referenced PDF crop.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from ..history_rag import fold

SCHEMA = "ayt-graph-prefill-v1"
CLAIM_TYPES = {
    "fact", "definition", "person_event", "date_event", "place_event",
    "chronology", "cause_effect", "scope", "institutional_decision",
    "military_strategy", "constitutional_principle",
}
RELATION_MAP = {
    "person_event": "gerceklestirdi", "date_event": "gerceklesti_tarih",
    "place_event": "gerceklesti_yer", "chronology": "once_geldi",
    "cause_effect": "neden_oldu", "definition": "tanımlar", "scope": "iliskilidir",
    "fact": "iliskilidir", "institutional_decision": "iliskilidir",
    "military_strategy": "iliskilidir", "constitutional_principle": "tanımlar",
}


def _node_id(label: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "-", fold(label)).strip("-")
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:8]
    return f"n-{compact[:48] or 'belirsiz'}-{digest}"


def _as_terms(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    return []


def _kinds(claim_type: str, count: int) -> list[str]:
    if claim_type == "person_event":
        return ["kisi", "olay"] + ["kavram"] * max(0, count - 2)
    if claim_type == "date_event":
        return ["tarih_donem", "olay"] + ["kavram"] * max(0, count - 2)
    if claim_type == "place_event":
        return ["yer", "olay"] + ["kavram"] * max(0, count - 2)
    if claim_type == "chronology":
        return ["olay"] * count
    if claim_type == "cause_effect":
        return ["olay"] * count
    return ["kavram"] * count


def _claim_map(plan: dict) -> dict[tuple[str, str], dict]:
    if plan.get("schema") != "ayt-evidence-plans-v1":
        raise ValueError("Beklenen kanıt planı şeması bulunamadı")
    rows = {}
    for case in plan.get("cases", []):
        for claim in case.get("evidence_claims", case.get("claims", [])):
            claim_type = claim.get("claim_type")
            if claim_type not in CLAIM_TYPES or not claim.get("id"):
                raise ValueError("Grafik ön doldurma için geçerli iddia türü gerekli")
            rows[(case["candidate_id"], claim["id"])] = claim
    return rows


def build(plan: dict, proposals: dict) -> dict:
    """Build an incomplete-by-default graph proposal queue."""
    if proposals.get("schema") != "ayt-evidence-bundle-proposals-v1":
        raise ValueError("Beklenen kanıt demeti öneri şeması bulunamadı")
    if plan.get("corpus_checksum") != proposals.get("corpus_checksum"):
        raise ValueError("Kanıt planı ve kaynak corpus sürümü eşleşmiyor")
    claims = _claim_map(plan)
    cases = []
    for proposal in proposals.get("proposals", []):
        edges, nodes, missing = [], {}, set(proposal.get("evidence_plan", {}).get("missing_claim_ids", []))
        for suggestion in proposal.get("suggestions", []):
            claim_id = suggestion.get("claim_id")
            claim = claims.get((proposal["candidate_id"], claim_id))
            if claim is None:
                raise ValueError("Önerinin kaynak planında karşılığı yok")
            if suggestion.get("claim_proof_mode") != "literal" or suggestion.get("claim_match_status") == "partial_candidate":
                missing.add(claim_id)
                continue
            labels = _as_terms(claim.get("entities"))
            if len(labels) < 2:
                # A source can still be a primary card, but cannot form a safe
                # relation edge without two declared endpoints.
                missing.add(claim_id)
                continue
            node_ids = []
            for label, kind in zip(labels, _kinds(claim["claim_type"], len(labels)), strict=True):
                identifier = _node_id(label)
                nodes.setdefault(identifier, {"id": identifier, "label": label, "kind": kind,
                                              "aliases": [], "proposal_only": True})
                node_ids.append(identifier)
            edge_id = f"e-{proposal['candidate_id']}-{claim_id}-{suggestion['chunk_id']}"
            edges.append({
                "id": edge_id, "claim_id": claim_id, "from_node": node_ids[0], "to_node": node_ids[1],
                "relation": RELATION_MAP[claim["claim_type"]], "source_key": suggestion["source_key"],
                "source_checksum": suggestion["source_checksum"], "chunk_id": suggestion["chunk_id"],
                "page": suggestion["page"], "bbox": suggestion["bbox"],
                "proof_mode": "literal", "review_status": "teacher_pdf_crop_required",
            })
        required = set(proposal.get("evidence_plan", {}).get("required_claim_ids", []))
        proposed = {edge["claim_id"] for edge in edges}
        missing.update(required - proposed)
        cases.append({
            "candidate_id": proposal["candidate_id"], "exam_year": proposal.get("exam_year"),
            "status": "teacher_graph_review_required" if edges else "graph_prefill_insufficient",
            "required_claim_ids": sorted(required), "covered_claim_ids": sorted(proposed),
            "missing_claim_ids": sorted(missing), "nodes": sorted(nodes.values(), key=lambda row: row["id"]),
            "edges": sorted(edges, key=lambda row: row["id"]),
        })
    return {
        "schema": SCHEMA, "corpus_checksum": proposals["corpus_checksum"],
        "question_source_checksum": proposals["question_source_checksum"], "cases": cases,
        "notice": "Private graph prefill. Every node and edge is a review proposal; no relationship is approved or student-visible.",
    }


def summarize(prefill: dict) -> dict:
    if prefill.get("schema") != SCHEMA:
        raise ValueError("Beklenen grafik ön doldurma şeması bulunamadı")
    cases = prefill.get("cases", [])
    required = sum(len(case["required_claim_ids"]) for case in cases)
    covered = sum(len(case["covered_claim_ids"]) for case in cases)
    edges = [edge for case in cases for edge in case["edges"]]
    return {
        "schema": "ayt-graph-prefill-report-v1", "corpus_checksum": prefill["corpus_checksum"],
        "question_source_checksum": prefill["question_source_checksum"],
        "summary": {
            "question_count": len(cases), "required_claim_count": required,
            "literal_claim_coverage": round(covered / required, 4) if required else 0.0,
            "edge_proposal_count": len(edges), "reviewable_case_count": sum(bool(case["edges"]) for case in cases),
            "insufficient_case_count": sum(not case["edges"] for case in cases),
            "relation_types": dict(sorted(Counter(edge["relation"] for edge in edges).items())),
            "unapproved_edge_count": sum(edge["review_status"] != "approved" for edge in edges),
        },
        "notice": "This is a coverage diagnostic, not graph precision/F1. Precision requires independent teacher PDF-crop labels.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = build(json.loads(args.plan.read_text(encoding="utf-8")),
                   json.loads(args.proposals.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    if args.report:
        args.report.write_text(json.dumps(summarize(result), ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
