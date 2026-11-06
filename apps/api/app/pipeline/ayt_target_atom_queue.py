"""Build an answer-free atom + context discovery queue for the AYT pilot.

This is deliberately a *review* tool.  It makes short factual atoms searchable
alongside explanatory paragraphs, but it never marks either as approved for a
student, runtime RAG, or QLoRA.  The queue is bound to the exact local textbook
checksum so an unavailable or replaced PDF cannot silently inherit approvals.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from ..history_rag import PreparedBM25
from .prepare_atom_retrieval_audit import need_plan

SCHEMA = "ayt-target-atom-context-review-queue-v1"
POOL_SCHEMA = "ayt-target-discovery-pool-v1"
CORPUS_SCHEMA = "multi-history-rag-v1"


def _usable(record: dict) -> bool:
    """Keep clean candidates, including manual-review prose, for *discovery*.

    ``manual_review`` means that a crop has not been approved, not that the
    paragraph is unsuitable for retrieval.  Treating it as a hard exclusion
    made most of the locally extracted textbook invisible.
    """
    return (
        bool(record.get("text", "").strip())
        and not record.get("quality", {}).get("warnings", [])
        and record.get("pre_review", {}).get("decision")
        in {"manual_review", "review_for_approval"}
    )


def _documents(book: dict, section_ids: set[str]) -> tuple[list[dict], list[dict]]:
    result: dict[str, list[dict]] = {"atom": [], "context": []}
    for granularity, key in (("atom", "evidence_atoms"), ("context", "context_chunks")):
        for record in book["index"].get(key, []):
            if record.get("section_id") not in section_ids or not _usable(record):
                continue
            heading = record.get("heading") or record.get("section_title", "")
            result[granularity].append(
                {
                    "id": f"{book['source_checksum']}:{granularity}:{record['id']}",
                    "record_id": record["id"],
                    "granularity": granularity,
                    "source_checksum": book["source_checksum"],
                    "source_name": book["source_name"],
                    "section_id": record["section_id"],
                    "section_title": record["section_title"],
                    "heading": record.get("heading"),
                    "page": record["page"],
                    "bbox": record["bbox"],
                    "text": f"{record['section_title']}\n{heading}\n{record['text']}",
                    "excerpt": record["text"],
                    "extraction_method": record.get("extraction_method"),
                    "pre_review_decision": record.get("pre_review", {}).get("decision"),
                    "review_status": "candidate_unverified",
                }
            )
    return result["atom"], result["context"]


def _rrf(*rankings: list[dict], constant: int = 60) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, record in enumerate(ranking, start=1):
            scores[record["id"]] += 1 / (constant + rank)
    return scores


def _diverse(records: list[dict], limit: int) -> list[dict]:
    """Avoid a single page crowding out complementary evidence."""
    selected: list[dict] = []
    seen_page_granularity: set[tuple[int, str]] = set()
    for record in records:
        page_key = (record["page"], record["granularity"])
        if page_key in seen_page_granularity:
            continue
        selected.append(record)
        seen_page_granularity.add(page_key)
        if len(selected) == limit:
            break
    return selected


def build(pool: dict, corpus: dict, *, candidate_limit: int = 12, first_stage_limit: int = 20) -> dict:
    if pool.get("schema") != POOL_SCHEMA:
        raise ValueError("AYT hedef keşif havuzu gerekli")
    if corpus.get("schema") != CORPUS_SCHEMA:
        raise ValueError("Sürümlü AYT corpus gerekli")
    if candidate_limit < 1 or first_stage_limit < candidate_limit:
        raise ValueError("Aday sınırları geçersiz")
    if pool.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("Havuz ve corpus checksum değerleri eşleşmiyor")
    section_ids = set(pool.get("candidate_section_ids", []))
    if len(section_ids) != 6:
        raise ValueError("Altı hedef bölüm gerekli")
    books = [book for book in corpus.get("books", []) if book.get("grade") == 12
             and book.get("source_role") == "primary_candidate"]
    if len(books) != 1:
        raise ValueError("Tek, doğrulanabilir 12. sınıf birincil kaynak gerekli")
    book = books[0]
    atoms, contexts = _documents(book, section_ids)
    if not atoms or not contexts:
        raise ValueError("Hedef bölümlerde hem atom hem bağlam adayı gerekli")
    atom_index, context_index = PreparedBM25(atoms), PreparedBM25(contexts)
    proposals = []
    for row in pool.get("rows", []):
        if row.get("transcription_status") != "private_teacher_review_required":
            proposals.append({"candidate_id": row.get("candidate_id"), "status": "blocked_transcription_quality", "suggestions": []})
            continue
        question = row.get("question", {})
        stem = question.get("stem", "")
        choices = [choice.get("text", "") for choice in question.get("choices", [])]
        plan = need_plan(row.get("topic", ""), stem)
        # The root drives the need plan; choices merely broaden candidate
        # discovery and remain answer-free.
        query = " ".join([plan["retrieval_query"], *choices]).strip()
        started = time.perf_counter()
        atom_ranked = atom_index.rank(query, first_stage_limit)
        context_ranked = context_index.rank(query, first_stage_limit)
        rrf = _rrf(atom_ranked, context_ranked)
        merged = {record["id"]: {**record, "retrieval_channels": [record["granularity"]]}
                  for record in [*atom_ranked, *context_ranked]}
        for record in atom_ranked + context_ranked:
            merged[record["id"]]["rrf_score"] = round(rrf[record["id"]], 6)
        ranked = sorted(
            merged.values(),
            key=lambda item: (-item["rrf_score"], -item["score"], item["page"], item["id"]),
        )
        selected = _diverse(ranked, candidate_limit)
        proposals.append(
            {
                "candidate_id": row["candidate_id"],
                "topic": row.get("topic"),
                "status": "candidate_evidence_requires_pdf_crop_review" if selected else "insufficient_candidate_set",
                "need_plan": plan,
                "candidate_counts": {"atom": len(atom_ranked), "context": len(context_ranked), "merged": len(ranked)},
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "suggestions": selected,
            }
        )
    return {
        "schema": SCHEMA,
        "corpus_checksum": corpus["corpus_checksum"],
        "source_binding": {"source_name": book["source_name"], "source_checksum": book["source_checksum"]},
        "target_section_ids": sorted(section_ids),
        "index_counts": {"atom": len(atoms), "context": len(contexts)},
        "retrieval": {"atom": "BM25", "context": "BM25", "fusion": "RRF(k=60)", "first_stage_limit": first_stage_limit},
        "proposals": proposals,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Candidate discovery only. Each selected item requires a PDF crop review before any use.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-limit", type=int, default=12)
    parser.add_argument("--first-stage-limit", type=int, default=20)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.pool), load(args.corpus), candidate_limit=args.candidate_limit,
                   first_stage_limit=args.first_stage_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"proposals": len(result["proposals"]), **result["index_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
