"""Render private PDF-crop review cards for source-local relation proposals."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import pymupdf

from .ayt_evidence_review_pack import _render_crop


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _books(corpus: dict) -> dict[str, dict]:
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Beklenen çok kitaplı corpus şeması bulunamadı")
    return {book["source_checksum"]: book for book in corpus.get("books", [])}


def build(proposals: dict, corpus: dict, source_root: Path, output: Path) -> dict:
    if proposals.get("schema") != "deepseek-source-relation-proposals-v1":
        raise ValueError("Beklenen kaynak ilişkisi öneri şeması bulunamadı")
    if proposals.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("İlişki önerisi ve corpus sürümü eşleşmiyor")
    books, rows, documents = _books(corpus), [], {}
    try:
        for source in proposals.get("sources", []):
            facts = [item for item in source.get("facts", [])
                     if item.get("review_status") == "teacher_pdf_crop_required"]
            if not facts:
                continue
            book = books.get(source.get("source_checksum"))
            if book is None:
                raise ValueError("İlişki önerisinin kaynak kitabı bulunamadı")
            pdf_path = source_root / book["source_name"]
            if not pdf_path.is_file() or _checksum(pdf_path) != book["source_checksum"]:
                raise ValueError("İlişki önerisinin PDF checksum'ı eşleşmiyor")
            document = documents.setdefault(book["source_checksum"], pymupdf.open(pdf_path))
            filename = f'{book["source_checksum"][:12]}-{source["chunk_id"]}.png'
            _render_crop(document, source["page"], source["bbox"], output / "crops" / filename)
            rows.append({
                "source_checksum": book["source_checksum"], "chunk_id": source["chunk_id"],
                "grade": book["grade"], "source_name": book["source_name"], "page": source["page"],
                "crop": f"crops/{filename}", "facts": facts,
            })
    finally:
        for document in documents.values():
            document.close()
    manifest = {
        "schema": "source-relation-review-pack-v1", "corpus_checksum": corpus["corpus_checksum"],
        "review_count": len(rows), "relation_count": sum(len(row["facts"]) for row in rows),
        "reviews": rows,
        "notice": "Private PDF-crop review only. No relation is approved, student-visible or eligible for RAG/QLoRA until a teacher verifies it.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    _write_html(manifest, output / "index.html")
    return manifest


def _write_html(manifest: dict, target: Path) -> None:
    blocks = []
    for row in manifest["reviews"]:
        facts = "".join(
            "<li><strong>" + html.escape(fact["subject"]) + "</strong> — "
            + html.escape(fact["relation"].replace("_", " ")) + " → <strong>"
            + html.escape(fact["object"]) + "</strong></li>"
            for fact in row["facts"]
        )
        blocks.append(
            f'<section><h2>{row["grade"]}. sınıf · s. {row["page"]}</h2>'
            f'<p>Kaynak: {html.escape(row["source_name"])} · parça: {html.escape(row["chunk_id"])}.</p>'
            f'<img src="{html.escape(row["crop"])}" alt="MEB PDF kaynak kesiti">'
            f'<h3>İncelenecek ilişki önerileri</h3><ul>{facts}</ul>'
            "<p>Her satırı PDF kesitiyle karşılaştırın: ilişki açıkça yazılı mı, iki uç doğru mu, "
            "kaynak bağlamı yeterli mi? Bu sayfa onay kaydı yazmaz.</p></section>"
        )
    target.write_text(
        "<!doctype html><meta charset=utf-8><title>Kaynak ilişkisi incelemesi</title>"
        "<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#102a43}"
        "section{border:1px solid #9fb3c8;border-radius:12px;padding:1rem;margin:1rem 0}"
        "img{max-width:100%;border:1px solid #bcccdc}li{margin:.5rem 0}</style>"
        "<h1>Kaynak ilişkisi PDF kesiti incelemesi</h1>"
        "<p>Bu paket soru ve cevap anahtarı içermez; hiçbir ilişkiyi onaylamaz.</p>" + "".join(blocks),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(json.loads(args.proposals.read_text(encoding="utf-8")),
          json.loads(args.corpus.read_text(encoding="utf-8")), args.source_root, args.output)


if __name__ == "__main__":
    main()
