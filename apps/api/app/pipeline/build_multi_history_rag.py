"""Build a private, checksum-bound manifest for multiple MEB history books."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..history_rag import build_index


def build(sources: dict[int, Path]) -> dict:
    """Build a candidate-only corpus from checksum-bound MEB textbooks.

    Grades are intentionally data-driven instead of hard-coded to the initial
    10--11 pilot.  This lets the review workflow add the 12th-grade İnkilap
    textbook without creating a second, incompatible corpus format.
    """
    if not sources:
        raise ValueError("En az bir MEB ders kitabı gerekli")
    books = []
    for grade, path in sorted(sources.items()):
        index = build_index(path)
        index_checksum = hashlib.sha256(json.dumps(
            index, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        books.append({"grade": grade, "source_name": path.name,
                      "source_checksum": index["source_checksum"],
                      "index_checksum": index_checksum,
                      "index": index})
    fingerprint = hashlib.sha256("\n".join(
        f'{book["grade"]}:{book["source_checksum"]}:{book["index_checksum"]}' for book in books
    ).encode()).hexdigest()
    return {"schema": "multi-history-rag-v1", "corpus_checksum": fingerprint,
            "books": books,
            "notice": "Private teacher-review corpus. Chunks are candidates, never student-visible without approval."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grade9", type=Path,
                        help="Deneysel kapsam için doğrulanmış 9. sınıf Tarih kitabı")
    parser.add_argument("--grade10", type=Path, required=True)
    parser.add_argument("--grade11", type=Path, required=True)
    parser.add_argument("--grade12", type=Path,
                        help="Doğrulanmış 12. sınıf T.C. İnkılap Tarihi kitabı")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = {10: args.grade10, 11: args.grade11}
    if args.grade9:
        sources[9] = args.grade9
    if args.grade12:
        sources[12] = args.grade12
    result = build(sources)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
