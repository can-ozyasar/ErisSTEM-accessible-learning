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
    return host.endswith(".meb.gov.tr") or host == "ogmmateryal.eba.gov.tr"


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


def register(pdf: Path, source_id: str, title: str, canonical_url: str) -> dict:
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise ValueError("Yerel ve .pdf uzantılı bir MEB ders kitabı gerekli")
    if not _official_meb_url(canonical_url):
        raise ValueError("Kaynak bağlantısı resmî MEB alan adında olmalı")
    if not source_id or len(source_id) < 8:
        raise ValueError("En az sekiz karakterlik kaynak kimliği gerekli")
    if len(title.strip()) < 8:
        raise ValueError("Kaynak başlığı gerekli")
    page_count = _valid_pdf_page_count(pdf)
    return {
        "schema": "ayt-history-meb-source-catalog-v1",
        "sources": [{
            "id": source_id,
            "kind": "meb_textbook",
            "title": title.strip(),
            "canonical_url": canonical_url,
            "source_checksum": _checksum(pdf),
            "page_count": page_count,
        }],
        "private_input": True,
        "pdf_exported": False,
        "notice": "Metadata only. Do not commit the PDF, upload it to Kaggle, or send it to an LLM API.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--canonical-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = register(args.pdf, args.source_id, args.title, args.canonical_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"source_id": args.source_id, "source_checksum": output["sources"][0]["source_checksum"]}))


if __name__ == "__main__":
    main()
