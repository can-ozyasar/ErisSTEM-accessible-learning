"""Project teacher-agent scoped official AYT questions into evidence discovery.

The projection keeps the agent decision as provenance but intentionally does
not interpret it as evidence approval.  A PDF crop and source-bound bundle
are still required before a question can reach RAG or QLoRA data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

INPUT_SCHEMA = "official-ayt-target-candidate-pool-v1"
AUDIT_SCHEMA = "teacher-official-ayt-target-audit-v1"
SCOPE_SCHEMA = "ayt-target-scope-manifest-v1"
OUTPUT_SCHEMA = "official-ayt-target-discovery-pool-v1"


def _checksum(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build(candidates: dict, audit: dict, scope: dict) -> dict:
    if candidates.get("schema") != INPUT_SCHEMA or audit.get("schema") != AUDIT_SCHEMA:
        raise ValueError("Resmî AYT aday havuzu ve öğretmen ajan denetimi gerekli")
    if scope.get("schema") != SCOPE_SCHEMA:
        raise ValueError("Checksum bağlı AYT hedef kapsamı gerekli")
    if audit.get("answer_key_accessed") or audit.get("worked_explanation_accessed"):
        raise ValueError("Cevap veya çözüm erişimli denetim projeksiyona giremez")
    if audit.get("reviewer_kind") != "history_teacher_agent_v1" or audit.get("is_human_teacher_approval") is not False:
        raise ValueError("Ajan öğretmen provenance kaydı zorunlu")
    allowed = {item["section_id"] for item in scope.get("sections", [])}
    if len(allowed) != 6:
        raise ValueError("Altı hedef bölüm gerekli")
    by_id = {row["candidate_id"]: row for row in candidates.get("rows", [])}
    rows = []
    for decision in audit.get("rows", []):
        target = decision.get("target_section_decision", {})
        if target.get("status") != "target_candidate":
            continue
        if decision.get("reviewer_kind") != "history_teacher_agent_v1":
            raise ValueError("Soru düzeyinde ajan öğretmen provenance kaydı zorunlu")
        section_ids = set(target.get("sections", []))
        if not section_ids or not section_ids <= allowed:
            raise ValueError("Hedef bölüm kararı allowlist dışında")
        original = by_id.get(decision.get("candidate_id"))
        if original is None:
            raise ValueError("Denetimdeki soru aday havuzunda bulunamadı")
        if original.get("answer_key_accessed") is not False or original.get("worked_explanation_accessed") is not False:
            raise ValueError("Soru cevap/çözümden yalıtılmış olmalı")
        rows.append({
            **original,
            "target_section_options": sorted(section_ids),
            "teacher_agent_review": {
                "reviewer_kind": "history_teacher_agent_v1",
                "error_or_relation_type": decision.get("error_or_relation_type"),
                "required_evidence_roles": decision.get("required_evidence_roles", []),
                "coaching_suitability": decision.get("coaching_suitability", {}),
                "quality_risks": decision.get("quality_risks", []),
                "source_review_priority": decision.get("source_review_priority"),
                "rationale": decision.get("rationale"),
            },
        })
    if not rows:
        raise ValueError("Hedef bölüm adayı yok")
    return {
        "schema": OUTPUT_SCHEMA,
        "source_checksum_set": sorted({row["source_checksum"] for row in rows}),
        "target_scope_checksum": _checksum(scope),
        "corpus_checksum": scope.get("source_binding", {}).get("corpus_checksum"),
        "candidate_section_ids": sorted(allowed),
        "rows": rows,
        "candidate_count": len(rows),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "reviewer_kind": "history_teacher_agent_v1",
        "is_human_teacher_approval": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Teacher-agent scope projection only. Source crop, evidence bundle and coaching approval are still pending.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.candidates), load(args.audit), load(args.scope))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidates": result["candidate_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
