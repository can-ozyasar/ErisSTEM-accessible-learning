"""Create an answer-free, checksum-bound MEB evidence review queue."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ..history_rag import PreparedBM25

SCHEMA = "ogm-ayt-real-question-evidence-queue-v1"


def _eligible(record: dict) -> bool:
    return (bool(record.get("text", "").strip()) and not record.get("quality", {}).get("warnings")
            and record.get("pre_review", {}).get("decision") in {"manual_review", "review_for_approval"})


def _documents(corpus: dict) -> list[dict]:
    docs = []
    for book in corpus.get("books", []):
        if book.get("source_role") == "supplementary_candidate":
            continue
        for granularity, key in (("atom", "evidence_atoms"), ("context", "context_chunks")):
            for record in book.get("index", {}).get(key, []):
                if not _eligible(record):
                    continue
                docs.append({
                    "id": f'{book["source_checksum"]}:{granularity}:{record["id"]}',
                    "source_checksum": book["source_checksum"], "source_name": book["source_name"],
                    "grade": book["grade"], "granularity": granularity, "record_id": record["id"],
                    "section_id": record["section_id"], "section_title": record["section_title"],
                    "page": record["page"], "bbox": record["bbox"], "heading": record.get("heading"),
                    "excerpt": record["text"],
                    "text": "\n".join(filter(None, (record["section_title"], record.get("heading"), record["text"]))),
                })
    if not docs:
        raise ValueError("kullanılabilir birincil MEB kanıt atomu bulunamadı")
    return docs


def _key(document: dict) -> tuple[str, int, tuple[float, ...]]:
    return document["source_checksum"], document["page"], tuple(document["bbox"])


def _diverse(ranked: list[dict], limit: int) -> list[dict]:
    selected, seen = [], set()
    for doc in ranked:
        key = _key(doc)
        if key in seen:
            continue
        selected.append(doc)
        seen.add(key)
        if len(selected) == limit:
            break
    return selected


def build(question_pack: dict, readiness: dict, corpus: dict, *, first_stage_limit: int = 24, candidate_limit: int = 12) -> dict:
    if question_pack.get("schema") != "ayt-target-question-candidates-v1":
        raise ValueError("gerçek soru aday paketi gerekli")
    if readiness.get("schema") != "ogm-ayt-real-question-pilot-readiness-v1":
        raise ValueError("onaylı gerçek soru hazırlık raporu gerekli")
    if readiness.get("source_checksum") != question_pack.get("source_checksum"):
        raise ValueError("soru paketi ve hazırlık raporu checksum değerleri uyuşmuyor")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("sürümlü MEB corpus gerekli")
    if candidate_limit < 1 or first_stage_limit < candidate_limit:
        raise ValueError("retrieval aday sınırları geçersiz")
    allowed = {row["id"] for row in readiness.get("approved_transcription_candidates", [])}
    rows = [row for row in question_pack.get("rows", []) if row.get("candidate_id") in allowed]
    if not rows or len(rows) != len(allowed):
        raise ValueError("hazırlık raporundaki soru kimlikleri aday paketiyle uyuşmuyor")
    documents = _documents(corpus)
    index = PreparedBM25(documents)
    proposals = []
    for row in rows:
        question = row["question"]
        query = " ".join([*(part.get("text", "") for part in question.get("parts", [])),
                          *(choice.get("text", "") for choice in question.get("choices", []))]).strip()
        started = time.perf_counter()
        ranked = index.rank(query, first_stage_limit)
        proposals.append({
            "candidate_id": row["candidate_id"], "deneme_number": row["deneme_number"],
            "question_number": question["number"], "question_text": query,
            "status": "candidate_evidence_requires_pdf_crop_review" if ranked else "insufficient_candidate_set",
            "retrieval_ms": round((time.perf_counter() - started) * 1000, 3),
            "suggestions": _diverse(ranked, candidate_limit),
        })
    return {
        "schema": SCHEMA, "question_source_checksum": question_pack["source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"], "question_count": len(proposals),
        "retrieval": {"method": "BM25", "first_stage_limit": first_stage_limit, "candidate_limit": candidate_limit,
                      "answer_key_used": False, "supplementary_source_used": False},
        "proposals": proposals, "runtime_enabled": False,
        "notice": "Answer-free candidate discovery only. A PDF-crop review must establish complete claim coverage before runtime use.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.questions), load(args.readiness), load(args.corpus))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"questions": result["question_count"], "runtime_enabled": False}))


if __name__ == "__main__":
    main()
