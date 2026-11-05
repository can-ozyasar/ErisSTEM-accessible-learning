"""Add an official supplementary history source for review-only coverage work."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..history_rag import build_index

ROLE = "supplementary_candidate"


def build(corpus: dict, source: Path) -> dict:
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Sürümlü çok kaynaklı tarih corpus'u gerekli")
    if source.suffix.lower() != ".pdf" or source.read_bytes()[:4] != b"%PDF":
        raise ValueError("Ek kaynak doğrulanmış PDF olmalı")
    index = build_index(source)
    checksum = index["source_checksum"]
    if any(book.get("source_checksum") == checksum for book in corpus.get("books", [])):
        raise ValueError("Ek kaynak zaten corpus içinde")
    index_checksum = hashlib.sha256(json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    supplementary = {
        "grade": 12,
        "source_name": source.name,
        "source_checksum": checksum,
        "index_checksum": index_checksum,
        "source_role": ROLE,
        "student_runtime_eligible": False,
        "qlora_eligible": False,
        "index": index,
    }
    books = [*corpus["books"], supplementary]
    fingerprint = hashlib.sha256("\n".join(
        f'{book["source_checksum"]}:{book.get("index_checksum", "")}:{book.get("source_role", "primary_candidate")}'
        for book in books
    ).encode()).hexdigest()
    return {
        "schema": "multi-history-rag-v1",
        "corpus_checksum": fingerprint,
        "books": books,
        "notice": ("Private coverage corpus. Supplementary candidates require PDF-crop and teacher approval "
                   "before runtime or QLoRA use."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.corpus.read_text(encoding="utf-8")), args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"books": len(result["books"]), "supplementary_chunks": len(result["books"][-1]["index"]["chunks"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
