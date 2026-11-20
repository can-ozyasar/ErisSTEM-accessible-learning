"""Render checksum-verified MEB crop cards for original-question source review."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import pymupdf


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sources(source_root: Path) -> dict[str, Path]:
    result = {}
    for path in source_root.glob("*.pdf"):
        checksum = _checksum(path)
        if checksum in result:
            raise ValueError("Aynı checksum taşıyan birden fazla kaynak PDF var")
        result[checksum] = path
    return result


def _render(document: pymupdf.Document, page: int, bbox: list[float], target: Path) -> None:
    if not 1 <= page <= document.page_count:
        raise ValueError("Kanıt sayfası PDF sınırları dışında")
    source_page = document[page - 1]
    clip = pymupdf.Rect(bbox) + (-18, -18, 18, 18)
    clip &= source_page.rect
    if clip.is_empty or clip.is_infinite:
        raise ValueError("Kanıt bbox değeri geçersiz")
    target.parent.mkdir(parents=True, exist_ok=True)
    source_page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), clip=clip, alpha=False).save(target)


def build(gate: dict, source_root: Path, output: Path) -> dict:
    if gate.get("schema") != "ayt-history-authoring-source-gate-v1":
        raise ValueError("Kaynak-yazım kapısı gerekli")
    if not isinstance(gate.get("queue_checksum"), str) or len(gate["queue_checksum"]) != 64:
        raise ValueError("Kaynak kuyruğu checksum'ı gerekli")
    paths = _sources(source_root)
    cards = gate.get("accepted_for_pdf_crop_review", [])
    if not cards:
        raise ValueError("PDF crop incelemesi için kabul edilmiş kaynak kartı yok")
    documents = {}
    rows = []
    try:
        for item in cards:
            card = item["card"]
            evidence = card["source_evidence"]
            checksum = evidence["source_checksum"]
            source = paths.get(checksum)
            if source is None:
                raise ValueError("Kaynak checksum'ına karşılık yerel MEB PDF bulunamadı")
            document = documents.setdefault(checksum, pymupdf.open(source))
            filename = f'{card["id"]}-{checksum[:12]}-p{evidence["page"]}.png'
            relative = Path("crops") / filename
            _render(document, evidence["page"], evidence["bbox"], output / relative)
            rows.append({"id": card["id"], "grade": evidence["grade"], "section_id": evidence["section_id"],
                         "section_title": evidence["section_title"], "source_name": evidence["source_id"],
                         "source_checksum": checksum, "page": evidence["page"], "bbox": evidence["bbox"],
                         "atom_id": evidence["atom_id"], "quote": evidence["quote"], "crop": relative.as_posix(),
                         "ai_verdict": item["ai_review"]["verdict"], "pdf_crop_checked": False,
                         "quality_checked": False, "status": "pdf_crop_review_required"})
    finally:
        for document in documents.values():
            document.close()
    return {"schema": "ayt-history-authoring-source-crop-pack-v1", "corpus_checksum": gate["corpus_checksum"],
            "queue_checksum": gate["queue_checksum"],
            "review_count": len(rows), "reviews": rows, "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Private PDF-crop review only. No evidence is approved and no question is created."}


def _write_html(pack: dict, output: Path) -> None:
    cards = "".join(
        f'<article><h2>{html.escape(row["id"])} · {row["grade"]}. sınıf · {html.escape(row["section_title"])}</h2>'
        f'<p>{html.escape(row["source_name"])} · s. {row["page"]} · {html.escape(row["atom_id"])}</p>'
        f'<img src="{html.escape(row["crop"])}" alt="MEB kaynak kanıt kırpımı">'
        f'<details><summary>Çıkarılan metin</summary><pre>{html.escape(row["quote"])}</pre></details>'
        '<p>Durum: PDF kırpımı ve metin eşleşmesi incelenmedi.</p></article>' for row in pack["reviews"])
    (output / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Özgün AYT kaynak crop incelemesi</title>"
        "<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem}article{border:1px solid #9fb3c8;border-radius:12px;padding:1rem;margin:1rem 0}img{max-width:100%;border:1px solid #bcccdc}pre{white-space:pre-wrap}</style>"
        "<h1>Özgün AYT Tarih kaynak crop inceleme paketi</h1><p>Bu paket soru, cevap veya onay içermez.</p>" + cards,
        encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    gate = json.loads(args.gate.read_text(encoding="utf-8"))
    result = build(gate, args.source_root, args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_html(result, args.output)
    print(json.dumps({"review_count": result["review_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
