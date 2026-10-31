"""Apply auditable, private retrieval-plan patches without approving evidence.

Patches may improve aliases, section hints and claim routing after a false
negative audit.  They cannot add a source approval, alter answer metadata or
remove the later PDF-crop / primary-evidence gate.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

_ALLOWED_OPS = {
    "replace_claim_match", "add_claim_aliases", "set_section_hints", "add_query_strategy",
    "merge_claims", "split_claim", "set_must_support", "add_routing_rule", "add_section_filter",
}


def _cases(plan: dict) -> list[dict]:
    return plan["cases"] if "cases" in plan else plan.get("plans", [])


def _claim_map(case: dict) -> dict[str, dict]:
    claims = case.get("evidence_claims", case.get("claims", []))
    return {claim["id"]: claim for claim in claims}


def _copy_queries(*claims: dict) -> list[str]:
    result = []
    for claim in claims:
        for value in claim.get("search_terms", claim.get("query_terms", [])):
            if value not in result:
                result.append(value)
    return result


def _apply_operation(case: dict, operation: dict) -> None:
    name = operation.get("op")
    if name not in _ALLOWED_OPS:
        raise ValueError("Kanıt planı yama işlemi desteklenmiyor")
    claims = case.get("evidence_claims", case.get("claims", []))
    by_id = _claim_map(case)
    claim_id = operation.get("claim_id")
    if name not in {"merge_claims", "split_claim", "add_routing_rule", "add_section_filter"} and claim_id not in by_id:
        raise ValueError("Yama bilinmeyen kanıt iddiasına bağlı")

    if name == "replace_claim_match":
        claim = by_id[claim_id]
        all_of = operation.get("all_of", [])
        any_of = operation.get("any_of", [])
        if not all_of:
            raise ValueError("Yama en az bir zorunlu ilişki grubu içermeli")
        claim["all_of_groups"] = all_of
        claim["any_of_groups"] = any_of
    elif name == "add_claim_aliases":
        claim = by_id[claim_id]
        aliases = operation.get("entity_alias_groups", [])
        if not aliases:
            raise ValueError("Yama en az bir eş anlam grubu içermeli")
        existing = claim.get("all_of_groups", [[entity] for entity in claim.get("entities", [])])
        # Preserve all existing mandatory groups.  Replace one only when an
        # alias phrase contains the same normalized first token, otherwise add
        # it as an explicit additional requirement.
        for alias_group in aliases:
            first = alias_group[0].casefold().split()[0]
            index = next((i for i, group in enumerate(existing)
                          if any(value.casefold().split()[0] == first for value in group)), None)
            if index is None:
                existing.append(alias_group)
            else:
                existing[index] = alias_group
        claim["all_of_groups"] = existing
    elif name == "set_section_hints":
        by_id[claim_id]["section_hints"] = operation.get("hints", [])
    elif name == "add_query_strategy":
        by_id[claim_id].setdefault("query_strategies", []).append({
            "strategy": operation.get("strategy"), "queries": operation.get("queries", []),
        })
    elif name == "set_must_support":
        by_id[claim_id]["must_support"] = bool(operation.get("value"))
    elif name == "split_claim":
        original = by_id.get(claim_id)
        pieces = operation.get("into", [])
        if original is None or len(pieces) < 2 or any(not piece.get("id") for piece in pieces):
            raise ValueError("Bölünecek kanıt iddiası geçersiz")
        if len({piece["id"] for piece in pieces}) != len(pieces):
            raise ValueError("Bölünen kanıt kimlikleri tekrarlı")
        expanded = []
        for piece in pieces:
            child = copy.deepcopy(original)
            child.update(copy.deepcopy(piece))
            child["all_of_groups"] = piece.get("all_of", child.get("all_of_groups", []))
            child.pop("all_of", None)
            expanded.append(child)
        claims[:] = [claim for claim in claims if claim["id"] != claim_id] + expanded
        requirements = case.get("support_requirements", {})
        required = requirements.get("all_must_support_claim_ids")
        if required is not None:
            requirements["all_must_support_claim_ids"] = [
                child["id"] for identifier in required for child in (expanded if identifier == claim_id else [{"id": identifier}])
            ]
        for discriminator in case.get("option_discriminators", []):
            discriminator["claim_ids"] = [
                child["id"] for identifier in discriminator.get("claim_ids", [])
                for child in (expanded if identifier == claim_id else [{"id": identifier}])
            ]
    elif name == "add_routing_rule":
        case.setdefault("discovery_routing_rules", []).append(operation.get("rule"))
    elif name == "add_section_filter":
        case.setdefault("discovery_section_filters", []).append({
            "section_title": operation.get("section_title"), "hard": bool(operation.get("hard")),
        })
    else:  # merge_claims
        identifiers = operation.get("claim_ids", [])
        if len(identifiers) < 2 or any(identifier not in by_id for identifier in identifiers):
            raise ValueError("Birleştirilecek kanıt iddiaları geçersiz")
        merged = copy.deepcopy(operation.get("into", {}))
        if not merged.get("id") or merged["id"] not in identifiers:
            raise ValueError("Birleşik kanıt kimliği geçersiz")
        original = [by_id[identifier] for identifier in identifiers]
        merged.setdefault("search_terms", _copy_queries(*original))
        merged.setdefault("stage", original[0].get("stage", "question_analysis"))
        claims[:] = [claim for claim in claims if claim["id"] not in identifiers]
        claims.append(merged)
        requirements = case.get("support_requirements", {})
        required = requirements.get("all_must_support_claim_ids")
        if required is not None:
            requirements["all_must_support_claim_ids"] = list(dict.fromkeys(
                merged["id"] if identifier in identifiers else identifier for identifier in required
            ))
        for discriminator in case.get("option_discriminators", []):
            discriminator["claim_ids"] = list(dict.fromkeys(
                merged["id"] if identifier in identifiers else identifier
                for identifier in discriminator.get("claim_ids", [])
            ))


def apply(plan: dict, patches: dict) -> dict:
    if plan.get("schema") not in {"ayt-evidence-plans-v1", "ayt-evidence-plans-priority-agent-draft-v1"}:
        raise ValueError("Beklenen kanıt planı şeması bulunamadı")
    if patches.get("schema") != "ayt-evidence-plan-patches-agent-draft-v1":
        raise ValueError("Beklenen kanıt planı yama şeması bulunamadı")
    if patches.get("is_teacher_approval") or patches.get("answer_key_accessed"):
        raise ValueError("Yama kaynağı onay veya cevap anahtarı taşıyamaz")
    result = copy.deepcopy(plan)
    by_id = {case["candidate_id"]: case for case in _cases(result)}
    for patch in patches.get("patches", []):
        case = by_id.get(patch.get("candidate_id"))
        if case is None:
            raise ValueError("Yama bilinmeyen soruya bağlı")
        for operation in patch.get("operations", []):
            _apply_operation(case, operation)
    result["schema"] = "ayt-evidence-plans-v1"
    result["derived_from"] = {"base_schema": plan["schema"], "patch_schema": patches["schema"]}
    result["is_teacher_approval"] = False
    result["answer_key_accessed"] = False
    result["notice"] = (
        "Private retrieval-plan derivative. Patches tune discovery only; they do not approve sources, "
        "remove crop review or allow evidence into student RAG/QLoRA."
    )
    result["cases"] = _cases(result)
    result.pop("plans", None)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--patches", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = apply(json.loads(args.plan.read_text(encoding="utf-8")),
                   json.loads(args.patches.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
