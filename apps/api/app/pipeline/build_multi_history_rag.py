"""Build a private, checksum-bound manifest for multiple MEB history books."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..history_rag import build_index


def build(sources: dict[int, Path]) -> dict:
    books = []
    for grade, path in sorted(sources.items()):
        index = build_index(path)
        books.append({"grade": grade, "source_name": path.name,
                      "source_checksum": index["source_checksum"],
                      "index": index})
    fingerprint = hashlib.sha256("\n".join(
        f'{book["grade"]}:{book["source_checksum"]}' for book in books).encode()).hexdigest()
    return {"schema": "multi-history-rag-v1", "corpus_checksum": fingerprint,
            "books": books,
            "notice": "Private teacher-review corpus. Chunks are candidates, never student-visible without approval."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grade10", type=Path, required=True)
    parser.add_argument("--grade11", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build({10: args.grade10, 11: args.grade11})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
