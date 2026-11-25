"""Register a local official MEB textbook without copying it into the repository.

The output is metadata only.  It binds the private local PDF bytes to an
official publication URL so a later AYT exam-pack manifest can reference the
same source checksum.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import pymupdf

MAX_SOURCE_PAGES = 600

def _official_meb_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host.endswith((".meb.gov.tr", ".eba.gov.tr"))


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _valid_pdf_page_count(pdf: Path) -> int:
    try:
        document = pymupdf.open(pdf)
    except pymupdf.FileDataError as error:
        raise ValueError("PDF ayrıştırılamadı") from error
    with document:
        if document.is_encrypted or not 1 <= document.page_count <= MAX_SOURCE_PAGES:
            raise ValueError(f"PDF sayfa sayısı 1 ile {MAX_SOURCE_PAGES} arasında ve şifresiz olmalı")
        return document.page_count


def register(pdf: Path, source_id: str, title: str, canonical_url: str, relative_path: str | None = None) -> dict:
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise ValueError("Yerel ve .pdf uzantılı bir MEB ders kitabı gerekli")
    if not _official_meb_url(canonical_url):
        raise ValueError("Kaynak bağlantısı resmî MEB alan adında olmalı")
    if not source_id or len(source_id) < 8:
        raise ValueError("En az sekiz karakterlik kaynak kimliği gerekli")
    if len(title.strip()) < 8:
        raise ValueError("Kaynak başlığı gerekli")
    mounted_path = Path(relative_path or pdf.name)
    if mounted_path.is_absolute() or ".." in mounted_path.parts or mounted_path.suffix.lower() != ".pdf":
        raise ValueError("Göreli, .pdf uzantılı bağlanmış kaynak yolu gerekli")
    page_count = _valid_pdf_page_count(pdf)
    return {
        "schema": "ayt-history-meb-source-catalog-v1",
        "sources": [{
            "id": source_id,
            "kind": "meb_textbook",
            "title": title.strip(),
            "canonical_url": canonical_url,
            "source_checksum": _checksum(pdf),
            "relative_path": mounted_path.as_posix(),
            "page_count": page_count,
        }],
        "private_input": True,
        "pdf_exported": False,
        "notice": "Metadata only. Do not commit the PDF, upload it to Kaggle, or send it to an LLM API.",
    }


def append_catalog(path: Path, source: dict) -> dict:
    """Append exactly one independently checksummed source without replacing a catalog."""
    if path.exists():
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if catalog.get("schema") != "ayt-history-meb-source-catalog-v1":
            raise ValueError("Mevcut kaynak kataloğu şeması geçersiz")
    else:
        catalog = {"schema": "ayt-history-meb-source-catalog-v1", "sources": [],
                   "private_input": True, "pdf_exported": False,
                   "notice": "Metadata only. Do not commit the PDF, upload it to Kaggle, or send it to an LLM API."}
    existing = catalog.get("sources", [])
    if any(item.get("id") == source["id"] or item.get("source_checksum") == source["source_checksum"] for item in existing):
        raise ValueError("Kaynak kimliği veya checksum katalogda zaten var")
    return {**catalog, "sources": [*existing, source]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--canonical-url", required=True)
    parser.add_argument("--relative-path", help="Compose içindeki /private/meb altında göreli PDF yolu")
    parser.add_argument("--append", action="store_true", help="Kaynağı mevcut metadata kataloğuna ekle")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registered = register(args.pdf, args.source_id, args.title, args.canonical_url, args.relative_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = append_catalog(args.output, registered["sources"][0]) if args.append else registered
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"source_id": args.source_id, "source_checksum": registered["sources"][0]["source_checksum"]}))


if __name__ == "__main__":
    main()
