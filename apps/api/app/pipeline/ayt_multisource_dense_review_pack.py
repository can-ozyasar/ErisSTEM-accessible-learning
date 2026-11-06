"""Render a private checksum-verified crop pack for a multi-book AYT audit."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
from pathlib import Path

import pymupdf

from .ayt_evidence_review_pack import _render_crop

QUEUE_SCHEMAS = {
    "official-ayt-multisource-dense-review-queue-v1": "ayt-multisource-dense-review-pack-v1",
    "official-ayt-full-multisource-dense-review-queue-v1": "ayt-full-multisource-dense-review-pack-v1",
}


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_source(value: str) -> tuple[str, Path]:
    checksum, separator, raw_path = value.partition("=")
    if not separator or len(checksum) != 64 or not raw_path:
        raise ValueError("Kaynak biçimi checksum=PDF_yolu olmalı")
    return checksum, Path(raw_path)


def _layout_tokens(text: str) -> list[str]:
    text = text.replace("\u00ad", "").casefold()
    text = "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))
    return re.findall(r"[a-zçğıöşü0-9]+", text)


def _assert_excerpt_in_crop(document: pymupdf.Document, page: int, bbox: list[float], excerpt: str) -> None:
    """Reject a crop whose source text does not contain the excerpt semantically.

    PDF extraction can reorder a heading and its paragraph or insert soft
    hyphens.  Token coverage tolerates those layout effects while still
    rejecting a crop from an unrelated page or coordinate.
    """
    crop_text = document[page - 1].get_text("text", clip=pymupdf.Rect(bbox))
    expected = _layout_tokens(excerpt)
    actual = set(_layout_tokens(crop_text))
    if not expected or sum(token in actual for token in expected) / len(expected) < 0.98:
        raise ValueError("PDF kesiti aday alıntının metin kapsamını karşılamıyor")


def build(queue: dict, sources: dict[str, Path], output: Path, *, per_question: int | None = None) -> dict:
    pack_schema = QUEUE_SCHEMAS.get(queue.get("schema"))
    if pack_schema is None:
        raise ValueError("Çok kaynaklı AYT inceleme kuyruğu gerekli")
    if per_question is not None and per_question < 1:
        raise ValueError("Her soru için en az bir kart gerekli")
    bindings = {item["source_checksum"] for item in queue["source_bindings"]}
    if set(sources) != bindings:
        raise ValueError("PDF kaynakları kuyruk checksum bağlarıyla tam eşleşmeli")
    for checksum, path in sources.items():
        if not path.is_file() or _checksum(path) != checksum:
            raise ValueError("PDF kaynak checksum doğrulaması başarısız")

    documents = {checksum: pymupdf.open(path) for checksum, path in sources.items()}
    try:
        rows, crop_count = [], 0
        for queue_row in queue["rows"]:
            cards = []
            for rank, suggestion in enumerate(queue_row["suggestions"][:per_question], start=1):
                checksum = suggestion["source_checksum"]
                if checksum not in documents:
                    raise ValueError("Kart tanımlanmamış kaynak PDF'sine bağlı")
                _assert_excerpt_in_crop(
                    documents[checksum], suggestion["page"], suggestion["bbox"], suggestion["excerpt"]
                )
                filename = f"{checksum[:12]}-{suggestion['record_id']}.png"
                relative = Path("crops") / filename
                _render_crop(documents[checksum], suggestion["page"], suggestion["bbox"], output / relative)
                cards.append(
                    {
                        "rank": rank,
                        "source_key": suggestion["source_key"],
                        "record_id": suggestion["record_id"],
                        "source_name": suggestion["source_name"],
                        "source_checksum": checksum,
                        "section_title": suggestion["section_title"],
                        "heading": suggestion.get("heading"),
                        "page": suggestion["page"],
                        "excerpt": suggestion["excerpt"],
                        "retrieval_method_ranks": suggestion["retrieval_method_ranks"],
                        "crop": relative.as_posix(),
                    }
                )
                crop_count += 1
            rows.append({"candidate_id": queue_row["candidate_id"], "need_plan": queue_row["need_plan"], "cards": cards})
    finally:
        for document in documents.values():
            document.close()

    manifest = {
        "schema": pack_schema,
        "corpus_checksum": queue["corpus_checksum"],
        "source_bindings": queue["source_bindings"],
        "review_count": len(rows),
        "crop_count": crop_count,
        "reviews": rows,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Private PDF-crop review aid only. Retrieval ranks are leads, not evidence; no answer key or worked solution is present.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_html(manifest, output / "index.html")
    return manifest


def _write_html(manifest: dict, target: Path) -> None:
    sections = []
    for row in manifest["reviews"]:
        cards = "".join(
            "<figure><figcaption>"
            f'#{card["rank"]} · {html.escape(card["source_name"])} · s. {card["page"]}<br>'
            f'{html.escape(card["section_title"])}'
            f'{" · " + html.escape(card["heading"]) if card.get("heading") else ""}'
            f'</figcaption><img src="{html.escape(card["crop"])}" alt="MEB tarih PDF kanıt kesiti"></figure>'
            for card in row["cards"]
        )
        need = row["need_plan"]
        sections.append(
            f'<section><h2>{html.escape(row["candidate_id"])}</h2>'
            f'<p><strong>İlişki ihtiyacı:</strong> {html.escape(str(need.get("relation_intent", "belirtilmedi")))}</p>'
            f'<p><strong>Aday varlıklar:</strong> {html.escape(", ".join(need.get("entity_hints", [])))}</p>'
            f'<div class="cards">{cards}</div><p>Her kartı PDF ile karşılaştırın; sıralama kanıt değildir.</p></section>'
        )
    target.write_text(
        "<!doctype html><meta charset=utf-8><title>Çok kaynaklı AYT kanıt incelemesi</title>"
        "<style>body{font:16px system-ui;max-width:1500px;margin:2rem auto;padding:0 1rem;color:#102a43}"
        "section{border:1px solid #9fb3c8;border-radius:12px;padding:1rem;margin:1rem 0}.cards{display:flex;gap:1rem;overflow:auto}"
        "figure{min-width:360px;margin:0}img{max-width:100%;border:1px solid #bcccdc}</style>"
        "<h1>Çok kaynaklı AYT tarih kanıt incelemesi</h1>"
        "<p>Bu paket cevap, cevap anahtarı ve çözümlü açıklama içermez; hiçbir kartı otomatik onaylamaz.</p>"
        + "".join(sections),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--source", action="append", default=[], help="checksum=PDF_yolu; iki kaynak için iki kez verin")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-question", type=int)
    args = parser.parse_args()
    sources = dict(_parse_source(value) for value in args.source)
    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    build(queue, sources, args.output, per_question=args.per_question)


if __name__ == "__main__":
    main()
