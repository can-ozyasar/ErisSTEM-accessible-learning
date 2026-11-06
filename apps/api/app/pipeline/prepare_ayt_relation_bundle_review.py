"""Prepare a source-bound relation-bundle review queue from top-20 retrieval leads.

A semantic retriever can find a useful *lead* without placing the full relation
in its first three results.  This module never turns that lead into a fact.  It
keeps the top-20 dense and lexical candidates, removes only exact duplicate
PDF crops, and presents a page-diverse private review queue for an agent or a
teacher to verify against the PDF.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "official-ayt-target-relation-bundle-review-queue-v1"
_ALLOWED_DECISIONS = {"direct", "indirect", "wrong", "insufficient"}


def _crop_key(document: dict) -> str:
    bbox = ":".join(f"{float(value):.2f}" for value in document["bbox"])
    return f"{document['source_checksum']}:{document['page']}:{bbox}"


def _assert_input(discovery: dict, rankings: dict, prior_audit: dict) -> None:
    if discovery.get("schema") != "ayt-target-dense-discovery-v1":
        raise ValueError("Checksum bağlı yoğun keşif girdisi gerekli")
    if rankings.get("schema") != "official-ayt-target-dense-discovery-rankings-v1":
        raise ValueError("Resmî AYT yoğun sıralama çıktısı gerekli")
    if prior_audit.get("schema") != "teacher-official-ayt-dense-audit-local12-v1":
        raise ValueError("Önceki PDF-kesiti denetimi gerekli")
    for payload in (discovery, rankings, prior_audit):
        if payload.get("answer_key_accessed") is not False or payload.get("worked_explanation_accessed") is not False:
            raise ValueError("Cevap anahtarı veya çözüm erişimli veri kullanılamaz")
    if rankings.get("corpus_checksum") != discovery.get("corpus_checksum"):
        raise ValueError("Sıralama ve keşif corpus checksum değerleri eşleşmiyor")
    if rankings.get("source_binding") != discovery.get("source_binding"):
        raise ValueError("Sıralama ve keşif kaynak bağları eşleşmiyor")
    audit_input = prior_audit.get("input", {})
    audit_source = prior_audit.get("source_checksum") or audit_input.get("source_checksum") or audit_input.get("source_binding", {}).get("source_checksum")
    audit_corpus = prior_audit.get("corpus_checksum") or audit_input.get("corpus_checksum")
    if audit_source != discovery["source_binding"]["source_checksum"] or audit_corpus != discovery["corpus_checksum"]:
        raise ValueError("Önceki denetim birincil kaynakla eşleşmiyor")


def _relation_focus(need_plan: dict) -> list[str]:
    """Expose the requested historical relationship without asserting it."""
    kind = need_plan.get("relation_intent", need_plan.get("relation_type", need_plan.get("need_type", "bilgi ilişkisi")))
    terms = need_plan.get("entity_hints", need_plan.get("entities", []))
    if not terms:
        terms = need_plan.get("time_hints", need_plan.get("keywords", []))
    return [str(kind), *[str(term) for term in terms[:6]]]


def _ranked_documents(
    document_by_id: dict[str, dict], ranks: dict[str, list[str]], first_stage_limit: int
) -> list[dict]:
    by_crop: dict[str, dict] = {}
    # Keep both methods visible. Each rank is metadata only, never evidence.
    for method in ("qwen_dense_tr", "bm25"):
        for rank, document_id in enumerate(ranks.get(method, [])[:first_stage_limit], start=1):
            document = document_by_id.get(document_id)
            if document is None:
                raise ValueError("Sıralama discovery belgesinin dışında kayıt içeriyor")
            key = _crop_key(document)
            row = by_crop.setdefault(key, {**document, "method_ranks": {}})
            row["method_ranks"][method] = rank
    return list(by_crop.values())


def _select_diverse(records: list[dict], limit: int) -> list[dict]:
    """Select by best rank while retaining room for complementary PDF pages."""
    def sort_key(row: dict) -> tuple[int, int, int, str]:
        ranks = row["method_ranks"]
        return (min(ranks.values()), sum(ranks.values()), row["page"], row["record_id"])

    selected: list[dict] = []
    seen_pages: set[tuple[str, int]] = set()
    for record in sorted(records, key=sort_key):
        page_key = (record["source_checksum"], record["page"])
        if page_key in seen_pages:
            continue
        selected.append(record)
        seen_pages.add(page_key)
        if len(selected) == limit:
            return selected
    # If the source has fewer pages than the review capacity, preserve other
    # distinct crops from those pages instead of padding nonexistent evidence.
    selected_keys = {_crop_key(row) for row in selected}
    for record in sorted(records, key=sort_key):
        if _crop_key(record) in selected_keys:
            continue
        selected.append(record)
        selected_keys.add(_crop_key(record))
        if len(selected) == limit:
            break
    return selected


def build(
    discovery: dict, rankings: dict, prior_audit: dict, *, first_stage_limit: int = 20, review_limit: int = 10
) -> dict:
    _assert_input(discovery, rankings, prior_audit)
    if first_stage_limit < 3 or review_limit < 3 or review_limit > first_stage_limit:
        raise ValueError("İlişki keşfi için aday sınırları geçersiz")
    documents = {row["id"]: row for row in discovery.get("documents", [])}
    queries = {row["id"]: row for row in discovery.get("queries", [])}
    prior = {row["candidate_id"]: row for row in prior_audit.get("records", [])}
    if set(queries) != set(rankings.get("rankings", {})) or set(queries) != set(prior):
        raise ValueError("Aynı kapalı soru kümesi için discovery, ranking ve denetim gerekli")

    rows = []
    for candidate_id, query in queries.items():
        before = prior[candidate_id]
        candidates = _ranked_documents(documents, rankings["rankings"][candidate_id], first_stage_limit)
        selected = _select_diverse(candidates, review_limit)
        rows.append(
            {
                "candidate_id": candidate_id,
                "prior_assessment": before["decision"],
                "prior_failure_diagnosis": before["failure_diagnosis"],
                "relation_focus": _relation_focus(query["need_plan"]),
                "need_plan": query["need_plan"],
                "first_stage_limit": first_stage_limit,
                "suggestions": [
                    {
                        "source_key": f"{row['source_checksum']}:{row['record_id']}",
                        "record_id": row["record_id"],
                        "granularity": row["granularity"],
                        "source_checksum": row["source_checksum"],
                        "source_name": row["source_name"],
                        "section_id": row["section_id"],
                        "section_title": row["section_title"],
                        "heading": row.get("heading"),
                        "page": row["page"],
                        "bbox": row["bbox"],
                        "excerpt": row["excerpt"],
                        "retrieval_method_ranks": row["method_ranks"],
                        "review_status": "private_pdf_crop_relation_review_required",
                    }
                    for row in selected
                ],
            }
        )
    return {
        "schema": SCHEMA,
        "corpus_checksum": discovery["corpus_checksum"],
        "source_binding": discovery["source_binding"],
        "embedding_model": rankings.get("embedding_model"),
        "retrieval": {"dense_method": "qwen_dense_tr", "lexical_method": "bm25", "first_stage_limit": first_stage_limit, "review_limit": review_limit, "deduplication": "exact_pdf_crop", "diversity": "one_per_page_before_extra_crops"},
        "rows": rows,
        "reviewer_kind_required": "history_teacher_agent_v1",
        "is_human_teacher_approval": False,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Top-20 relation discovery queue. Rank and relation_focus are leads only; exact PDF-crop review must validate every bundle before any graph, RAG or QLoRA use.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--prior-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first-stage-limit", type=int, default=20)
    parser.add_argument("--review-limit", type=int, default=10)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.discovery), load(args.rankings), load(args.prior_audit), first_stage_limit=args.first_stage_limit, review_limit=args.review_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"questions": len(result["rows"]), "cards": sum(len(row["suggestions"]) for row in result["rows"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
