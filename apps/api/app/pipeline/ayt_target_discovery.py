"""Prepare an answer-free, section-bounded discovery set for AYT evidence review.

This is intentionally a narrowing step: the two broad OGM headings are only
used to obtain candidates.  Each retained question still needs a reviewer to
assign exactly one target section and to approve its PDF evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "ayt-target-discovery-pool-v1"
SOURCE_SCHEMA = "ogm-ayt-private-transcription-v1"
TARGET_SCHEMA = "ayt-target-scope-manifest-v1"
ALLOWED_TOPICS = {"Millî Mücadele", "Atatürkçülük ve Türk İnkılabı"}


def build(transcriptions: dict, target_scope: dict, corpus: dict) -> tuple[dict, dict]:
    """Return private question and corpus subsets, both checksum-bound."""
    if transcriptions.get("schema") != SOURCE_SCHEMA:
        raise ValueError("Private AYT transkripsiyon havuzu gerekli")
    if target_scope.get("schema") != TARGET_SCHEMA:
        raise ValueError("AYT hedef kapsam manifesti gerekli")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("MEB corpus şeması geçersiz")
    binding = target_scope.get("source_binding", {})
    if binding.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("Hedef kapsam ve corpus sürümü eşleşmiyor")
    target_ids = {section["section_id"] for section in target_scope.get("sections", [])}
    if len(target_ids) != 6:
        raise ValueError("Tam altı hedef MEB bölümü gerekli")
    book = next(
        (
            item
            for item in corpus.get("books", [])
            if item.get("source_checksum") == binding.get("meb_source_checksum")
        ),
        None,
    )
    if book is None or book.get("grade") != 12:
        raise ValueError("Hedef MEB kitabı corpus içinde bulunamadı")
    rows = [row for row in transcriptions.get("rows", []) if row.get("topic") in ALLOWED_TOPICS]
    if not rows or len({row.get("candidate_id") for row in rows}) != len(rows):
        raise ValueError("Hedef aday sorular benzersiz ve boş olmayan bir küme olmalı")
    pool = {
        "schema": SCHEMA,
        "source_checksum": transcriptions["source_checksum"],
        "target_scope_checksum": binding.get("scope_report_checksum"),
        "corpus_checksum": corpus["corpus_checksum"],
        "candidate_section_ids": sorted(target_ids),
        "rows": rows,
        "candidate_count": len(rows),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Geniş konu etiketi yalnız keşif filtresidir. Her soru, PDF kanıt incelemesinden önce alt bölüme atanmış veya kabul edilmiş sayılmaz.",
    }
    section_chunks = [
        chunk for chunk in book["index"].get("chunks", []) if chunk.get("section_id") in target_ids
    ]
    if not section_chunks:
        raise ValueError("Hedef bölümlerde kanıt adayı bulunamadı")
    discovery_book = {**book, "index": {**book["index"], "chunks": section_chunks}}
    discovery_corpus = {
        "schema": "multi-history-rag-v1",
        "corpus_checksum": corpus["corpus_checksum"],
        "books": [discovery_book],
        "scope": {"grade": 12, "section_ids": sorted(target_ids)},
        "notice": "Private section-bounded discovery corpus. Candidate chunks remain unapproved.",
    }
    return pool, discovery_corpus


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--target-scope", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--pool-output", type=Path, required=True)
    parser.add_argument("--corpus-output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    pool, discovery_corpus = build(
        load(args.transcriptions), load(args.target_scope), load(args.corpus)
    )
    for path, body in ((args.pool_output, pool), (args.corpus_output, discovery_corpus)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "questions": pool["candidate_count"],
                "chunks": len(discovery_corpus["books"][0]["index"]["chunks"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
