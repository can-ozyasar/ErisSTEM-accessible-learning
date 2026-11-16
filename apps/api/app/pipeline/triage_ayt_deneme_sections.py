"""Rank textbook sections for private AYT deneme questions, without approval.

The full textbook index competes with the six target sections. This prevents
every unrelated question from being forced into the target scope. Only the
question stem is searched; choices, keys and worked solutions are excluded.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from ..history_rag import PreparedBM25
from ..question_scope import visual_dependency_reasons
from .ayt_target_atom_queue import _documents


def _stem(question: dict) -> str:
    return " ".join(part.get("text", "") for part in question.get("parts", []))


def build(pool: dict, corpus: dict, scope: dict, *, document_limit: int = 160) -> dict:
    if pool.get("schema") != "ayt-target-question-candidates-v1":
        raise ValueError("AYT deneme aday havuzu gerekli")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Sürümlü MEB corpus'u gerekli")
    if pool.get("answer_key_accessed") is not False or pool.get("worked_explanation_accessed") is not False:
        raise ValueError("Cevap veya çözüm erişimli havuz kullanılamaz")
    if corpus.get("corpus_checksum") != scope.get("source_binding", {}).get("corpus_checksum"):
        raise ValueError("Kapsam ve MEB corpus checksum'ı uyuşmuyor")
    if document_limit < 10:
        raise ValueError("İlk aşama belge sınırı çok küçük")
    books = [book for book in corpus.get("books", [])
             if book.get("grade") == scope.get("grade")
             and book.get("source_checksum") == scope["source_binding"]["meb_source_checksum"]]
    if len(books) != 1:
        raise ValueError("Kapsama bağlı tek bir MEB kitabı gerekli")
    book = books[0]
    target = {section["section_id"] for section in scope["sections"]}
    all_sections = {section["id"] for section in book["index"]["sections"]}
    if not target <= all_sections:
        raise ValueError("Hedef bölüm kitap indeksinde yok")
    atoms, contexts = _documents(book, all_sections)
    documents = [*atoms, *contexts]
    index = PreparedBM25(documents)
    rows = []
    for row in pool.get("rows", []):
        question = row["question"]
        if visual_dependency_reasons(question):
            raise ValueError(f"Görsel soru metin havuzuna girmiş: {row['candidate_id']}")
        stem = _stem(question)
        if not stem.strip():
            raise ValueError(f"Soru kökü boş: {row['candidate_id']}")
        ranked = index.rank(stem, limit=document_limit)
        by_section: dict[str, list[dict]] = defaultdict(list)
        for document in ranked:
            if len(by_section[document["section_id"]]) < 3:
                by_section[document["section_id"]].append(document)
        proposals = sorted(
            ({"section_id": section_id,
              "score": round(sum(item["score"] for item in items), 3),
              "evidence_candidates": [{"id": item["id"], "page": item["page"],
                                       "granularity": item["granularity"],
                                       "score": item["score"]} for item in items],
              "is_target_section": section_id in target}
             for section_id, items in by_section.items()),
            key=lambda item: (-item["score"], item["section_id"]),
        )[:5]
        rows.append({
            "candidate_id": row["candidate_id"],
            "question_source_checksum": row["source_checksum"],
            "question_page": row["page"],
            "lexical_section_hints": row.get("target_section_options", []),
            "section_proposals": proposals,
            "target_in_top3": any(item["is_target_section"] for item in proposals[:3]),
            "status": "private_pdf_crop_and_section_review_required",
        })
    return {
        "schema": "ayt-deneme-full-book-section-triage-v1",
        "question_source_checksum": pool["source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"],
        "meb_source_checksum": book["source_checksum"],
        "target_section_ids": sorted(target),
        "document_count": len(documents),
        "query_policy": "question_stem_only_full_book_competition",
        "rows": rows,
        "question_count": len(rows),
        "target_top3_review_count": sum(item["target_in_top3"] for item in rows),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "BM25 section proposals only; all PDF question crops, section labels and source evidence require separate review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    report = build(load(args.pool), load(args.corpus), load(args.scope))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"question_count": report["question_count"],
                      "target_top3_review_count": report["target_top3_review_count"],
                      "document_count": report["document_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
