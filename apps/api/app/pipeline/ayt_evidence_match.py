"""Propose MEB evidence for private AYT Tarih-2 review candidates.

This is deliberately a *teacher-workspace* tool.  It never reads an answer
key, marks a source as approved, or writes question text to a public/runtime
index.  Its output remains in ``data/private`` and every proposal carries the
source-book checksum that produced it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..history_rag import rank_chunks


def _question_text(question: dict) -> str:
    """Use only visible stem and option text; answer metadata is ignored."""
    parts = [part.get("text", "") for part in question.get("parts", [])]
    choices = [choice.get("text", "") for choice in question.get("choices", [])]
    return " ".join(piece.strip() for piece in [*parts, *choices] if piece.strip())


def _candidate(chunk: dict, book: dict) -> dict:
    return {
        "chunk_id": chunk["id"],
        "grade": book["grade"],
        "source_name": book["source_name"],
        "source_checksum": book["source_checksum"],
        "section_id": chunk["section_id"],
        "section_title": chunk["section_title"],
        "page": chunk["page"],
        "bbox": chunk["bbox"],
        "score": chunk["score"],
        "text": chunk["text"],
        "pre_review": chunk.get("pre_review", {}),
        "review_status": "candidate",
    }


def build(question_candidates: dict, corpus: dict, limit: int = 8) -> dict:
    """Create checksum-bound review suggestions across the installed books."""
    if question_candidates.get("schema") != "ayt-tarih2-candidates-v1":
        raise ValueError("Beklenen AYT Tarih-2 aday şeması bulunamadı")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Beklenen çok kitaplı MEB corpus şeması bulunamadı")
    if limit < 1:
        raise ValueError("limit en az 1 olmalı")

    rows = []
    for source_candidate in question_candidates.get("candidates", []):
        candidate_id = source_candidate["candidate_id"]
        if source_candidate.get("year_status") != "bound":
            rows.append({
                "candidate_id": candidate_id,
                "status": "blocked_until_exam_year_review",
                "exam_year": None,
                "suggestions": [],
            })
            continue

        query = _question_text(source_candidate.get("question", {}))
        ranked = []
        for book in corpus.get("books", []):
            for item in rank_chunks(book["index"].get("chunks", []), query, limit=limit):
                ranked.append(_candidate(item, book))
        ranked.sort(key=lambda item: (-item["score"], item["grade"], item["page"], item["chunk_id"]))
        suggestions = ranked[:limit]
        rows.append({
            "candidate_id": candidate_id,
            "status": "teacher_review_required" if suggestions else "insufficient_evidence",
            "exam_year": source_candidate["exam_year"],
            "suggestions": suggestions,
        })

    return {
        "schema": "ayt-evidence-proposals-v1",
        "question_source_checksum": question_candidates["source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"],
        "proposal_count": len(rows),
        "proposals": rows,
        "notice": (
            "Private teacher-review output. Proposals are not approvals; no answer key was read "
            "and no passage may reach student RAG or QLoRA without PDF-crop review."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    result = build(json.loads(args.questions.read_text(encoding="utf-8")),
                   json.loads(args.corpus.read_text(encoding="utf-8")), args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
