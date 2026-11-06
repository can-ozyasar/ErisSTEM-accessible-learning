"""Render a private, answer-free PDF crop pack for graph approval."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import pymupdf


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render(document: pymupdf.Document, page: int, bbox: list[float], target: Path) -> None:
    if not isinstance(page, int) or page < 1 or page > len(document):
        raise ValueError("Geçersiz PDF sayfası")
    clip = pymupdf.Rect(bbox)
    clip &= document[page - 1].rect
    if clip.is_empty or clip.is_infinite:
        raise ValueError("Geçersiz PDF koordinatı")
    target.parent.mkdir(parents=True, exist_ok=True)
    document[page - 1].get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), clip=clip, alpha=False).save(target)


def build(corpus: dict, source_root: Path, output: Path, *, limit: int | None = None) -> dict:
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Corpus şeması geçersiz")
    documents: dict[str, pymupdf.Document] = {}
    rows = []
    try:
        for book in corpus.get("books", []):
            source = source_root / str(book.get("source_name", ""))
            checksum = str(book.get("source_checksum", ""))
            if not source.is_file() or _checksum(source) != checksum:
                raise ValueError("Kaynak PDF checksum eşleşmiyor")
            documents[checksum] = pymupdf.open(source)
            for chunk in book.get("index", {}).get("chunks", []):
                if limit is not None and len(rows) >= limit:
                    break
                crop = f"crops/{checksum[:12]}-{chunk['id']}.png"
                _render(documents[checksum], int(chunk["page"]), chunk["bbox"], output / crop)
                rows.append({"source_checksum": checksum, "source_name": book["source_name"],
                             "chunk_id": str(chunk["id"]), "section_id": chunk.get("section_id"),
                             "section_title": chunk.get("section_title", ""), "page": chunk["page"],
                             "bbox": chunk["bbox"], "text": chunk.get("text", ""), "crop": crop,
                             "decision": "pending"})
            if limit is not None and len(rows) >= limit:
                break
    finally:
        for document in documents.values():
            document.close()
    manifest = {"schema": "ayt-graph-teacher-approval-pack-v1",
                "corpus_checksum": corpus["corpus_checksum"], "review_count": len(rows),
                "reviews": rows,
                "notice": "Private PDF crop review aid. This pack does not approve graph evidence."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    blocks = []
    for row in rows:
        blocks.append(
            f'<section><h2>{html.escape(row["chunk_id"])} · s. {row["page"]} · '
            f'{html.escape(row["section_title"])}</h2><p>{html.escape(row["text"])}</p>'
            f'<img src="{html.escape(row["crop"])}" alt="PDF kanıt kesiti"></section>')
    (output / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>AYT grafik onay paketi</title>"
        "<style>body{font:16px system-ui;max-width:1200px;margin:2rem auto}section{border:1px solid #9fb3c8;padding:1rem;margin:1rem 0;border-radius:10px}img{max-width:100%;border:1px solid #bcccdc}</style>"
        "<h1>AYT bilgi grafiği PDF onay paketi</h1>"
        "<p>Her kesiti kaynak PDF ile karşılaştırın. Bu sayfa karar kaydetmez ve onay vermez.</p>"
        + "".join(blocks), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    manifest = build(json.loads(args.corpus.read_text(encoding="utf-8")), args.source_root,
                     args.output, limit=args.limit)
    print(json.dumps({"schema": manifest["schema"], "review_count": manifest["review_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
