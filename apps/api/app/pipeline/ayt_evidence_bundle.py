"""Build review-only, multi-passage evidence bundles for AYT history questions.

A whole-question keyword score is not evidence: a history question can require
one passage for the core fact and another for chronology, causation, location,
or an option-confusion distinction.  This module consumes a *teacher-authored
claim plan* and searches each claim independently.  It emits a variable-sized,
checksum-bound review bundle and refuses to call it complete until every
mandatory claim has a candidate.

The plan is private.  It may be drafted by an agent, but it remains a review
plan rather than a source approval.  Neither answer keys nor final answers are
read by this module.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..history_rag import terms
from .ayt_constraint_probe import _covered, _eligible_chunks

ALLOWED_ROLES = {"primary", "context", "relation", "contrast"}
ALLOWED_CLAIM_TYPES = {
    "fact", "definition", "person_event", "date_event", "place_event", "chronology",
    "cause_effect", "scope", "institutional_decision", "military_strategy",
    "constitutional_principle",
}
ALLOWED_STAGES = {"question_analysis", "recall", "evidence_link", "choice_check"}
ALLOWED_OUTCOMES = {"reretrieve", "insufficient", "blocked"}


def _case_claims(case: dict) -> list[dict]:
    """Accept the early ``claims`` draft name and the reviewed schema name."""
    return case["evidence_claims"] if "evidence_claims" in case else case.get("claims", [])


def _plan_cases(plan: dict) -> list[dict]:
    """Read both the production plan name and the agent's explicit draft form."""
    return plan["cases"] if "cases" in plan else plan.get("plans", [])


def _claim_all_of(claim: dict) -> list[str]:
    # The teacher draft names historical entities.  Requiring every entity is
    # intentionally conservative: a passage that mentions only one side of a
    # claimed relationship cannot be treated as direct relation evidence.
    return claim.get("all_of", claim.get("entities", []))


def _claim_query_terms(claim: dict) -> list[str]:
    values = list(claim.get("query_terms", claim.get("search_terms", [])))
    for strategy in claim.get("query_strategies", []):
        for query in strategy.get("queries", []):
            values.extend(query if isinstance(query, list) else [query])
    return values


def _all_groups(claim: dict) -> list[list[str]]:
    """Mandatory groups; terms inside one group are aliases, groups are AND."""
    if claim.get("all_of_groups"):
        return _normalise_groups(claim["all_of_groups"])
    return _normalise_groups(_claim_all_of(claim))


def _any_groups(claim: dict) -> list[list[str]]:
    """At least one alias group must match when optional anchors are supplied."""
    if claim.get("any_of_groups"):
        return _normalise_groups(claim["any_of_groups"])
    return _normalise_groups(claim.get("any_of", []))


def _normalise_groups(groups: list) -> list[list[str]]:
    """Repair nested agent draft groups into explicit alias groups.

    A nested group means several mandatory groups, while a flat string list is
    one group of aliases.  Rejecting or silently stringifying nested input
    would hide an instruction-plan defect and produce misleading matches.
    """
    normalised: list[list[str]] = []
    for group in groups:
        if isinstance(group, str):
            normalised.append([group])
        elif all(isinstance(value, str) for value in group):
            normalised.append(group)
        elif all(isinstance(value, list) for value in group):
            normalised.extend(_normalise_groups(group))
        else:
            raise ValueError("Kanıt ilişki grubu yalnız metin veya metin listesi içermeli")
    return normalised


def _group_terms(groups: list[list[str]]) -> set[str]:
    return set(terms(" ".join(alias for group in groups for alias in group)))


def _phrase_matches(observed: set[str], phrase: str) -> bool:
    phrase_terms = set(terms(phrase))
    return bool(phrase_terms) and _covered(phrase_terms, observed) == phrase_terms


def _group_matches(observed: set[str], aliases: list[str]) -> bool:
    return any(_phrase_matches(observed, alias) for alias in aliases)


def _matches_terms(observed: set[str], claim: dict) -> bool:
    """Require all core terms and at least one optional anchor, if supplied."""
    all_groups = _all_groups(claim)
    any_groups = _any_groups(claim)
    return all(_group_matches(observed, aliases) for aliases in all_groups) and (
        not any_groups or any(_group_matches(observed, aliases) for aliases in any_groups)
    )


def _title_overlap(chunk: dict, section_hints: list[str]) -> int:
    observed = set(terms(chunk.get("section_title", "")))
    wanted = set(terms(" ".join(section_hints)))
    return len(_covered(wanted, observed))


def _score(book: dict, chunk: dict, claim: dict) -> tuple[int, int, int]:
    observed = set(terms(chunk["text"]))
    required = _group_terms([*_all_groups(claim), *_any_groups(claim)])
    query = set(terms(" ".join(_claim_query_terms(claim))))
    # The exact claim gate is checked first.  These transparent tie breakers
    # only decide among passages that already carry every mandatory term.
    claim_hits = len(_covered(required, observed))
    query_hits = len(_covered(query, observed))
    return claim_hits, _title_overlap(chunk, claim.get("section_hints", [])), query_hits


def _group_coverage(observed: set[str], claim: dict) -> tuple[int, int]:
    groups = _all_groups(claim)
    return sum(_group_matches(observed, aliases) for aliases in groups), len(groups)


def _candidate(book: dict, chunk: dict, claim: dict, score: tuple[int, int, int]) -> dict:
    return {
        "claim_id": claim["id"],
        "suggested_role": claim["role"],
        "source_key": f'{book["source_checksum"]}:{chunk["id"]}',
        "chunk_id": chunk["id"],
        "source_name": book["source_name"],
        "source_checksum": book["source_checksum"],
        "grade": book["grade"],
        "section_id": chunk["section_id"],
        "section_title": chunk["section_title"],
        "page": chunk["page"],
        "bbox": chunk["bbox"],
        "text": chunk["text"],
        "pre_review": chunk.get("pre_review", {}),
        "score_components": {
            "claim_term_coverage": score[0],
            "section_hint_overlap": score[1],
            "query_term_overlap": score[2],
        },
        "review_status": "candidate",
    }


def _rank_claim(pool: list[tuple[dict, dict]], claim: dict, per_claim: int) -> list[dict]:
    rows = []
    for book, chunk in pool:
        observed = set(terms(chunk["text"]))
        if not _matches_terms(observed, claim):
            continue
        score = _score(book, chunk, claim)
        rows.append((_candidate(book, chunk, claim, score), score))
    rows.sort(key=lambda row: (
        -row[1][0], -row[1][1], -row[1][2], row[0]["grade"], row[0]["page"], row[0]["chunk_id"]
    ))
    # A review queue should expose alternate evidence, not three blocks from a
    # single paragraph.  Keep one per PDF page until every distinct page has
    # been considered; no fixed per-question cap exists.
    selected, seen_pages = [], set()
    for item, _score_value in rows:
        page_key = (item["source_checksum"], item["page"])
        if page_key in seen_pages:
            continue
        seen_pages.add(page_key)
        selected.append(item)
        if len(selected) == per_claim:
            break
    return selected


def _rank_partial_discovery(pool: list[tuple[dict, dict]], claim: dict, per_claim: int) -> list[dict]:
    """Find leads for an uncovered claim without presenting them as evidence.

    This path deliberately records how much of the planned relation is
    missing.  It lets a reviewer or a later alias/source repair inspect useful
    leads while preserving the hard completeness gate used by the product.
    """
    query = set(terms(" ".join(_claim_query_terms(claim))))
    rows = []
    for book, chunk in pool:
        observed = set(terms(chunk["text"]))
        groups_covered, group_count = _group_coverage(observed, claim)
        query_hits = len(_covered(query, observed))
        if not groups_covered and query_hits < 2:
            continue
        score = (groups_covered, _title_overlap(chunk, claim.get("section_hints", [])), query_hits)
        item = _candidate(book, chunk, claim, score)
        item["review_status"] = "discovery_candidate"
        item["claim_match_status"] = "partial_candidate"
        item["entity_groups_covered"] = groups_covered
        item["entity_group_count"] = group_count
        rows.append((item, score))
    rows.sort(key=lambda row: (
        -row[1][0], -row[1][1], -row[1][2], row[0]["grade"], row[0]["page"], row[0]["chunk_id"]
    ))
    selected, seen_pages = [], set()
    for item, _score_value in rows:
        page_key = (item["source_checksum"], item["page"])
        if page_key in seen_pages:
            continue
        seen_pages.add(page_key)
        selected.append(item)
        if len(selected) == per_claim:
            break
    return selected


def _case_pool(pool: list[tuple[dict, dict]], case: dict) -> list[tuple[dict, dict]]:
    """Apply only explicit hard section filters during private discovery."""
    filters = [item.get("section_title", "") for item in case.get("discovery_section_filters", [])
               if item.get("hard")]
    if not filters:
        return pool
    filtered = []
    for book, chunk in pool:
        title_terms = set(terms(chunk.get("section_title", "")))
        if any(_covered(set(terms(expected)), title_terms) == set(terms(expected)) for expected in filters):
            filtered.append((book, chunk))
    # An absent/renamed heading must not silently erase the discovery queue.
    # Keep the full pool and report the filter as ineffective through the
    # unchanged result; a teacher can then repair the title alias explicitly.
    return filtered or pool


def _validate_plan(question_candidates: dict, corpus: dict, plan: dict, per_claim: int) -> None:
    if question_candidates.get("schema") != "ayt-tarih2-candidates-v1":
        raise ValueError("Beklenen AYT soru aday şeması bulunamadı")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Beklenen çok kitaplı corpus şeması bulunamadı")
    if plan.get("schema") not in {
        "ayt-evidence-plans-v1", "ayt-evidence-plans-priority-agent-draft-v1",
    }:
        raise ValueError("Beklenen öğretmen kanıt planı şeması bulunamadı")
    if plan.get("question_source_checksum") != question_candidates.get("source_checksum"):
        raise ValueError("Kanıt planı ve soru checksum'ları eşleşmiyor")
    if plan.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("Kanıt planı ve corpus checksum'ları eşleşmiyor")
    if per_claim < 1:
        raise ValueError("Her kanıt iddiası için en az bir aday gerekli")

    question_ids = {row["candidate_id"] for row in question_candidates.get("candidates", [])
                    if row.get("year_status") == "bound"}
    seen_cases = set()
    for case in _plan_cases(plan):
        candidate_id = case.get("candidate_id")
        if candidate_id not in question_ids or candidate_id in seen_cases:
            raise ValueError("Kanıt planı soru kimliği geçersiz")
        seen_cases.add(candidate_id)
        claims = _case_claims(case)
        if not claims:
            raise ValueError("Her soru için en az bir kanıt iddiası gerekli")
        seen_claims = set()
        for claim in claims:
            if not claim.get("id") or claim["id"] in seen_claims:
                raise ValueError("Kanıt iddiası kimliği geçersiz")
            seen_claims.add(claim["id"])
            if claim.get("role") not in ALLOWED_ROLES:
                raise ValueError("Kanıt iddiası rolü geçersiz")
            if claim.get("claim_type") and claim["claim_type"] not in ALLOWED_CLAIM_TYPES:
                raise ValueError("Kanıt iddiası türü geçersiz")
            stage = claim.get("stage_min", claim.get("stage"))
            if stage and stage not in ALLOWED_STAGES:
                raise ValueError("Kanıt iddiası aşaması geçersiz")
            if not _all_groups(claim) and not _any_groups(claim):
                raise ValueError("Kanıt iddiası en az bir arama dayanağı içermeli")
        discriminator_ids = set()
        for discriminator in case.get("option_discriminators", []):
            identifier = discriminator.get("id")
            if not identifier or identifier in discriminator_ids:
                raise ValueError("Şık ayırıcı kimliği geçersiz")
            discriminator_ids.add(identifier)
            if not set(discriminator.get("claim_ids", [])) <= seen_claims:
                raise ValueError("Şık ayırıcı bilinmeyen kanıt iddiasına bağlı")
        requirements = case.get("support_requirements", {})
        required_claims = set(requirements.get("all_must_support_claim_ids", []))
        if not required_claims <= seen_claims:
            raise ValueError("Destek gereksinimi bilinmeyen kanıt iddiasına bağlı")
        required_discriminators = set(requirements.get("required_discriminator_ids", []))
        if not required_discriminators <= discriminator_ids:
            raise ValueError("Destek gereksinimi bilinmeyen şık ayırıcısına bağlı")
        abstain = case.get("abstain_gate", {})
        outcomes = [abstain["outcome"]] if abstain.get("outcome") else abstain.get("allowed_outcomes", [])
        if any(outcome not in ALLOWED_OUTCOMES for outcome in outcomes):
            raise ValueError("Çekimser kalma sonucu geçersiz")


def build(question_candidates: dict, corpus: dict, plan: dict, per_claim: int = 3,
          include_manual_review: bool = False) -> dict:
    """Create a complete-by-claims, never-approved private review proposal."""
    _validate_plan(question_candidates, corpus, plan, per_claim)
    pool = _eligible_chunks(corpus, include_manual_review)
    questions = {row["candidate_id"]: row for row in question_candidates.get("candidates", [])}
    proposals = []
    for case in _plan_cases(plan):
        claims = _case_claims(case)
        case_pool = _case_pool(pool, case)
        ranked_by_claim = {claim["id"]: _rank_claim(case_pool, claim, per_claim) for claim in claims}
        discovery_by_claim = {
            claim["id"]: (ranked_by_claim[claim["id"]] or _rank_partial_discovery(case_pool, claim, per_claim))
            for claim in claims
        }
        required_ids = case.get("support_requirements", {}).get(
            "all_must_support_claim_ids",
            [claim["id"] for claim in claims if claim.get("must_support", claim.get("required", True))],
        )
        missing = [claim_id for claim_id in required_ids if not ranked_by_claim[claim_id]]

        # A passage may serve two claims. Keep it once and retain every linked
        # claim/role so a reviewer sees the proposed relationship explicitly.
        merged: dict[str, dict] = {}
        for claim in claims:
            for candidate in discovery_by_claim[claim["id"]]:
                candidate.setdefault("claim_match_status", "complete_candidate")
                previous = merged.get(candidate["source_key"])
                if previous is None:
                    candidate["claim_ids"] = [claim["id"]]
                    candidate["suggested_roles"] = [claim["role"]]
                    merged[candidate["source_key"]] = candidate
                    continue
                if claim["id"] not in previous["claim_ids"]:
                    previous["claim_ids"].append(claim["id"])
                if claim["role"] not in previous["suggested_roles"]:
                    previous["suggested_roles"].append(claim["role"])
        suggestions = sorted(merged.values(), key=lambda item: (
            -len(item["claim_ids"]), -item["score_components"]["claim_term_coverage"],
            -item["score_components"]["section_hint_overlap"], item["grade"], item["page"], item["chunk_id"]
        ))
        status = "teacher_review_required" if not missing else (
            "reretrieve_required" if suggestions else "insufficient_evidence"
        )
        proposals.append({
            "candidate_id": case["candidate_id"],
            "exam_year": questions[case["candidate_id"]]["exam_year"],
            "status": status,
            "evidence_plan": {
                "topic_labels": case.get("topic_labels", []),
                "claim_count": len(claims),
                "required_claim_ids": required_ids,
                "missing_claim_ids": missing,
                "complete": not missing,
                "option_discriminators": case.get("option_discriminators", []),
                "evidence_policy": case.get("evidence_policy", {}),
                "abstain_gate": case.get("abstain_gate", {}),
            },
            "suggestions": suggestions,
        })
    return {
        "schema": "ayt-evidence-bundle-proposals-v1",
        "question_source_checksum": question_candidates["source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"],
        "proposal_count": len(proposals),
        "proposals": proposals,
        "notice": (
            "Private claim-planned review output. An agent or teacher plan is a retrieval aid, not "
            "an approval. Every proposed passage needs PDF-crop review; incomplete required claims "
            "must remain insufficient evidence and cannot enter student RAG or QLoRA."
            + (" Manual-review passages were included for discovery only." if include_manual_review else "")
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-claim", type=int, default=3)
    parser.add_argument("--include-manual-review", action="store_true")
    args = parser.parse_args()
    result = build(
        json.loads(args.questions.read_text(encoding="utf-8")),
        json.loads(args.corpus.read_text(encoding="utf-8")),
        json.loads(args.plan.read_text(encoding="utf-8")),
        args.per_claim,
        args.include_manual_review,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
