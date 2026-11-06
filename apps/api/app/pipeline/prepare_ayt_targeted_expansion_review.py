"""Build a wider, answer-free BM25 review queue for retrieval-miss questions."""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from ..history_rag import PreparedBM25

SCHEMA = "official-ayt-full-targeted-expansion-review-queue-v1"
AUDIT_DECISIONS = {"insufficient", "indirect"}


def _clean_query(value: str) -> str:
    value = re.sub(r"\b(?:hük\s+meti|harek\s+tımız|genelgesi\s+nde|Osmanlı\s+Devleti\s+ne)\b", lambda m: m.group(0).replace(" ", ""), value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def _queries(row: dict) -> list[str]:
    plan = row.get("need_plan", {})
    entities = " ".join(plan.get("entity_hints", []))
    relation = str(plan.get("relation_intent", ""))
    topic = str(plan.get("topic", ""))
    original = _clean_query(str(plan.get("retrieval_query", "")))
    return list(dict.fromkeys(filter(None, [original, f"{topic} {entities} {relation}", f"{entities} {topic}"])))


def build(discovery: dict, queue: dict, audit: dict, *, first_stage_limit: int = 100, review_limit: int = 30) -> dict:
    if discovery.get("schema") != "ayt-full-multisource-dense-discovery-v1":
        raise ValueError("Tam AYT discovery corpus gerekli")
    if queue.get("corpus_checksum") != discovery.get("corpus_checksum") or audit.get("input", {}).get("corpus_checksum") != discovery.get("corpus_checksum"):
        raise ValueError("Discovery, kuyruk ve audit corpus checksum değerleri eşleşmeli")
    docs = discovery.get("documents", [])
    index = PreparedBM25(docs)
    queue_by_id = {row["candidate_id"]: row for row in queue.get("rows", [])}
    audit_rows = {row["candidate_id"]: row for row in audit.get("records", [])}
    rows = []
    for candidate_id, audit_row in audit_rows.items():
        if audit_row.get("decision") not in AUDIT_DECISIONS:
            continue
        source_row = queue_by_id[candidate_id]
        ranked_by_id: dict[str, dict] = {}
        method_ranks: dict[str, dict[str, int]] = defaultdict(dict)
        for method, query in enumerate(_queries(source_row), start=1):
            for position, document in enumerate(index.rank(query, first_stage_limit), start=1):
                document_id = document["id"]
                method_ranks[document_id][f"query_{method}"] = position
                existing = ranked_by_id.setdefault(document_id, document)
                if document["score"] > existing["score"]:
                    ranked_by_id[document_id] = document
        ranked = sorted(ranked_by_id.values(), key=lambda item: (min(method_ranks[item["id"]].values()), item["page"], item["id"]))
        selected, seen_pages = [], set()
        for document in ranked:
            page_key = (document["source_checksum"], document["page"])
            if page_key in seen_pages:
                continue
            selected.append(document)
            seen_pages.add(page_key)
            if len(selected) == review_limit:
                break
        rows.append({
            "candidate_id": candidate_id,
            "need_plan": source_row["need_plan"],
            "prior_decision": audit_row["decision"],
            "prior_failure_diagnosis": audit_row.get("failure_diagnosis"),
            "first_stage_limit": first_stage_limit,
            "query_variants": _queries(source_row),
            "suggestions": [{
                "source_key": f"{doc['source_checksum']}:{doc['record_id']}",
                "record_id": doc["record_id"], "granularity": doc["granularity"],
                "source_checksum": doc["source_checksum"], "source_name": doc["source_name"],
                "section_id": doc["section_id"], "section_title": doc["section_title"],
                "heading": doc.get("heading"), "page": doc["page"], "bbox": doc["bbox"],
                "excerpt": doc["excerpt"], "retrieval_method_ranks": method_ranks[doc["id"]],
                "review_status": "private_pdf_crop_review_required",
            } for doc in selected],
        })
    return {
        "schema": SCHEMA, "corpus_checksum": discovery["corpus_checksum"],
        "source_bindings": discovery["source_bindings"],
        "retrieval": {"method": "BM25", "query_variants": "original_cleaned_plus_entity_relation", "first_stage_limit": first_stage_limit, "review_limit": review_limit, "deduplication": "one_per_source_page_before_extra_crops"},
        "rows": rows, "reviewer_kind_required": "history_teacher_agent_v1",
        "is_human_teacher_approval": False, "answer_key_accessed": False,
        "worked_explanation_accessed": False, "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Expanded candidate discovery only; prior decisions are diagnostic labels, not answers or source approval.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", type=Path, required=True); parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first-stage-limit", type=int, default=100); parser.add_argument("--review-limit", type=int, default=30)
    args = parser.parse_args(); load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    result = build(load(args.discovery), load(args.queue), load(args.audit), first_stage_limit=args.first_stage_limit, review_limit=args.review_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"questions": len(result["rows"]), "cards": sum(len(x["suggestions"]) for x in result["rows"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
