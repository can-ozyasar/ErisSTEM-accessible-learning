"""Check private OGM review cards against the exact MEB PDF revision.

This checks identity, location and transcription. It does not judge whether
the passage proves a historical claim or grant teacher approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import pymupdf

SCHEMA = "ogm-ayt-source-integrity-v1"


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00ad", "").replace("\u200b", "")).strip().casefold()


def _checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect(queue: dict, corpus: dict, source_root: Path) -> dict:
    if queue.get("schema") not in {"ogm-ayt-evidence-review-queue-v3",
                                   "ogm-ayt-manual-source-discovery-v1"}:
        raise ValueError("OGM inceleme veya keşif kuyruğu gerekli")
    if queue.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("MEB corpus sürümü değişmiş")
    books = {book["source_checksum"]: book for book in corpus.get("books", [])}
    chunks = {checksum: {chunk["id"]: chunk for chunk in book["index"]["chunks"]}
              for checksum, book in books.items()}
    documents: dict[str, pymupdf.Document] = {}
    results = []
    try:
        for row in queue.get("proposals", []):
            for item in row.get("suggestions", []):
                checksum = item["source_checksum"]
                book = books.get(checksum)
                if book is None or book["source_name"] != item["source_name"]:
                    raise ValueError("Kart corpus kaynak kimliğiyle eşleşmiyor")
                if checksum not in documents:
                    source = source_root / book["source_name"]
                    if not source.is_file() or _checksum(source) != checksum:
                        raise ValueError("MEB PDF checksum doğrulaması başarısız")
                    documents[checksum] = pymupdf.open(source)
                chunk = chunks[checksum].get(item["chunk_id"])
                if chunk is None or any(item.get(key) != chunk.get(key)
                                        for key in ("text", "page", "bbox", "section_title")):
                    raise ValueError("Kart güncel kaynak parçasıyla eşleşmiyor")
                pdf = documents[checksum]
                page_number = item["page"]
                if not isinstance(page_number, int) or not 1 <= page_number <= len(pdf):
                    raise ValueError("Kaynak sayfası geçersiz")
                page = pdf[page_number - 1]
                box = pymupdf.Rect(item["bbox"])
                if box.is_empty or not page.rect.contains(box):
                    raise ValueError("Kaynak koordinatı sayfa dışında")
                visible = page.get_text("text", clip=box)
                similarity = SequenceMatcher(None, _normalized(item["text"]), _normalized(visible)).ratio()
                results.append({
                    "candidate_id": row["candidate_id"],
                    "source_key": f'{checksum}:{item["chunk_id"]}',
                    "pdf_text_similarity": round(similarity, 4),
                    "crop_text_present": bool(visible.strip()),
                    "needs_crop_review": similarity < 0.85,
                })
    finally:
        for document in documents.values():
            document.close()
    return {
        "schema": SCHEMA, "source_checksum": queue["source_checksum"],
        "corpus_checksum": queue["corpus_checksum"],
        "source_queue_schema": queue["schema"],
        "question_count": len(queue.get("proposals", [])), "card_count": len(results),
        "low_similarity_count": sum(item["needs_crop_review"] for item in results),
        "cards": results, "runtime_enabled": False, "qlora_enabled": False,
        "notice": "PDF identity and crop text only; historical support and teacher approval remain unverified.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inspect(json.loads(args.queue.read_text(encoding="utf-8")),
                     json.loads(args.corpus.read_text(encoding="utf-8")), args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("question_count", "card_count", "low_similarity_count")}))


if __name__ == "__main__":
    main()
