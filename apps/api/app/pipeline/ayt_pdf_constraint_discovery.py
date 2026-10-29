"""Find constraint-matching PDF blocks that the normal RAG index omitted.

This is a private diagnostic path.  It deliberately bypasses the normal
candidate-length and document-type filters only to create a PDF-crop review
queue.  Its output is never an approved corpus and cannot be used at runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

from ..history_rag import _clean, block_layout, chunk_quality, source_review_recommendation
from .ayt_constraint_probe import _matches, _rank_matches


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _section_for_page(book: dict, page: int) -> dict | None:
    return next((section for section in book["index"].get("sections", [])
                 if section["start"] <= page <= section["end"]), None)


def _raw_blocks(book: dict, source_root: Path) -> list[tuple[dict, dict]]:
    source = source_root / book["source_name"]
    if not source.is_file() or _checksum(source) != book["source_checksum"]:
        raise ValueError("MEB kaynak PDF checksum'ı eşleşmiyor")
    blocks = []
    with pymupdf.open(source) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            section = _section_for_page(book, page_number)
            if section is None:
                continue
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0:
                    continue
                lines = ["".join(span["text"] for span in line["spans"])
                         for line in block["lines"]]
                text = _clean(" ".join(lines))
                if not text:
                    continue
                bbox = [round(float(value), 2) for value in block["bbox"]]
                identity = hashlib.sha256(
                    f'{book["source_checksum"]}:{page_number}:{bbox}:{text}'.encode()
                ).hexdigest()[:20]
                layout = block_layout(lines)
                blocks.append((book, {
                    "id": identity, "section_id": section["id"], "section_title": section["title"],
                    "page": page_number, "bbox": bbox, "text": text,
                    "quality": chunk_quality(text), "layout": layout,
                    "pre_review": source_review_recommendation(text, layout),
                    "raw_pdf_fallback": True,
                }))
    return blocks


def _suggestion(book: dict, chunk: dict, clause: dict) -> dict:
    return {
        "chunk_id": chunk["id"], "grade": book["grade"], "source_name": book["source_name"],
        "source_checksum": book["source_checksum"], "section_id": chunk["section_id"],
        "section_title": chunk["section_title"], "page": chunk["page"], "bbox": chunk["bbox"],
        "score": chunk["score"], "text": chunk["text"], "pre_review": chunk["pre_review"],
        "review_status": "candidate", "constraint_clause_id": clause["id"],
        "raw_pdf_fallback": True, "source_type": chunk["pre_review"].get("source_type", "raw_pdf_block"),
    }


def build(corpus: dict, constraints: dict, source_root: Path, per_clause: int = 2) -> dict:
    """Create a checksum-bound review queue from raw matching PDF blocks."""
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Beklenen çok kitaplı corpus şeması bulunamadı")
    if constraints.get("schema") != "ayt-evidence-constraints-v1":
        raise ValueError("Beklenen kanıt kısıt şeması bulunamadı")
    if constraints.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("Kısıt ve corpus checksum'ları eşleşmiyor")
    if per_clause < 1:
        raise ValueError("Her kısıt için en az bir aday gerekli")
    pool = [item for book in corpus.get("books", []) for item in _raw_blocks(book, source_root)]
    rows = []
    for case in constraints.get("cases", []):
        clauses = case.get("required_clauses", [])
        if not clauses or any(not clause.get("id") for clause in clauses):
            raise ValueError("Her kısıt vakasında kimlikli zorunlu madde gerekli")
        suggestions, missing = [], []
        for clause in clauses:
            matches = [(book, chunk) for book, chunk in pool if _matches(chunk, clause)]
            ranked = _rank_matches(matches, clause, case.get("query_terms", []), per_clause)
            if not ranked:
                missing.append(clause["id"])
                continue
            suggestions.extend(_suggestion(book, chunk, clause) for book, chunk in ranked)
        deduped = {}
        for order, suggestion in enumerate(suggestions):
            key = (suggestion["source_checksum"], suggestion["chunk_id"])
            entry = (suggestion["score"], order, suggestion)
            if key not in deduped:
                deduped[key] = entry
                continue
            existing = deduped[key][2]
            clause_ids = existing.setdefault("constraint_clause_ids", [existing["constraint_clause_id"]])
            if suggestion["constraint_clause_id"] not in clause_ids:
                clause_ids.append(suggestion["constraint_clause_id"])
            if entry[0] > deduped[key][0]:
                suggestion["constraint_clause_ids"] = clause_ids
                deduped[key] = entry
        ordered = [entry[2] for entry in sorted(
            deduped.values(), key=lambda entry: (-entry[0], entry[1], entry[2]["page"], entry[2]["chunk_id"])
        )]
        rows.append({
            "candidate_id": case["candidate_id"], "exam_year": case.get("exam_year"),
            "status": "teacher_review_required" if not missing else "insufficient_evidence",
            "constraint_gate": {"required_clause_ids": [clause["id"] for clause in clauses],
                                "missing_clause_ids": missing, "complete": not missing},
            "suggestions": ordered,
        })
    return {
        "schema": "ayt-evidence-proposals-v1",
        "question_source_checksum": constraints["question_source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"], "proposal_count": len(rows), "proposals": rows,
        "notice": (
            "Private raw-PDF fallback discovery. It bypasses normal candidate filtering only for "
            "PDF-crop inspection; no output is approved for student RAG, evaluation or QLoRA."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--constraints", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-clause", type=int, default=2)
    args = parser.parse_args()
    result = build(json.loads(args.corpus.read_text(encoding="utf-8")),
                   json.loads(args.constraints.read_text(encoding="utf-8")),
                   args.source_root, args.per_clause)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
