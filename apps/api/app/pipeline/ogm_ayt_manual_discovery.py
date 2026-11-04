"""Search excluded MEB passages for private PDF review, never runtime evidence."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ..history_rag import PreparedBM25
from .ogm_ayt_evidence_queue import _claim_terms, _query, _topic_pool
from .ogm_ayt_retrieval_gold import source_key

SCHEMA = "ogm-ayt-manual-source-discovery-v1"


def build(transcriptions: dict, queue: dict, corpus: dict, limit: int = 6) -> dict:
    if (transcriptions.get("schema") != "ogm-ayt-private-transcription-v1"
            or queue.get("schema") != "ogm-ayt-evidence-review-queue-v3"
            or corpus.get("schema") != "multi-history-rag-v1"
            or queue.get("source_checksum") != transcriptions.get("source_checksum")
            or queue.get("corpus_checksum") != corpus.get("corpus_checksum")):
        raise ValueError("Soru, kanıt kuyruğu ve MEB corpus sürümleri eşleşmiyor")
    if limit < 1:
        raise ValueError("Aday sınırı pozitif olmalı")
    pool = [(book, chunk) for book in corpus["books"] if book.get("grade") in {10, 11, 12}
            for chunk in book["index"].get("chunks", [])]
    items = [{**chunk, "id": f'{book["source_checksum"]}:{chunk["id"]}',
              "_book": book, "_chunk_id": chunk["id"]} for book, chunk in pool]
    index = PreparedBM25(items)
    by_id = {item["id"]: item for item in items}
    queue_by_id = {row["candidate_id"]: row for row in queue["proposals"]}
    proposals = []
    for row in transcriptions["rows"]:
        started = time.perf_counter()
        if row.get("transcription_status") != "private_teacher_review_required":
            continue
        original = queue_by_id[row["candidate_id"]]
        existing = {source_key(item) for item in original.get("suggestions", [])}
        stem = " ".join(sorted(_claim_terms(row)))
        queries = {"full": _query(row), "stem": stem or row["question"]["stem"]}
        for choice in row["question"]["choices"]:
            queries[f'choice_{choice["label"]}'] = f'{stem} {choice["text"]}'
        ranks = {name: index.rank(query, limit=min(50, len(items)))
                 for name, query in queries.items()}
        scores: dict[str, float] = {}
        routes: dict[str, list[str]] = {}
        for name, hits in ranks.items():
            weight = 1.0 if name in {"full", "stem"} else 0.35
            for position, hit in enumerate(hits, 1):
                if hit["id"] in existing:
                    continue
                scores[hit["id"]] = scores.get(hit["id"], 0) + weight / (60 + position)
                routes.setdefault(hit["id"], []).append(name)
        topic_keys = {(book["source_checksum"], chunk["id"])
                      for book, chunk in _topic_pool(pool, row["topic"])}
        ranked_ids = sorted(scores, key=lambda key: (-scores[key], key))[:limit]
        suggestions = []
        for key in ranked_ids:
            item = by_id[key]
            book = item["_book"]
            suggestions.append({
                "source_checksum": book["source_checksum"], "source_name": book["source_name"],
                "grade": book["grade"], "chunk_id": item["_chunk_id"],
                "page": item["page"], "bbox": item["bbox"], "text": item["text"],
                "section_title": item["section_title"],
                "pre_review_decision": item.get("pre_review", {}).get("decision"),
                "pre_review_reasons": item.get("pre_review", {}).get("reasons", []),
                "quality_warnings": item.get("quality", {}).get("warnings", []),
                "in_topic_section": (book["source_checksum"], item["_chunk_id"]) in topic_keys,
                "query_routes": routes[key], "fusion_score": round(scores[key], 6),
                "review_status": "private_pdf_discovery_only",
            })
        proposals.append({"candidate_id": row["candidate_id"], "topic": row["topic"],
                          "retrieval_ms": round((time.perf_counter() - started) * 1000, 2),
                          "suggestions": suggestions})
    return {"schema": SCHEMA, "source_checksum": queue["source_checksum"],
            "corpus_checksum": queue["corpus_checksum"], "proposals": proposals,
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Private discovery includes manual-review passages. No candidate is approved evidence.",
            }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    result = build(json.loads(args.transcriptions.read_text(encoding="utf-8")),
                   json.loads(args.queue.read_text(encoding="utf-8")),
                   json.loads(args.corpus.read_text(encoding="utf-8")), args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"question_count": len(result["proposals"]),
                      "card_count": sum(len(row["suggestions"]) for row in result["proposals"])}))


if __name__ == "__main__":
    main()
