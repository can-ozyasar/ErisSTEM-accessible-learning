"""PDF içeriğini dönüştürmeden sayfa kapsamı seçimi için private envanter üretir."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

from .pdf_text_layer import PdfSafetyError, _read_and_validate


def inventory(path: Path, source_root: Path) -> dict:
    _, content = _read_and_validate(path, source_root)
    checksum = hashlib.sha256(content).hexdigest()
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        if pdf.is_encrypted:
            raise PdfSafetyError("Şifreli PDF envanteri çıkarılmaz")
        pages = []
        for number, page in enumerate(pdf, start=1):
            text = page.get_text("text")
            pages.append(
                {
                    "page": number,
                    "text_characters": len(text.strip()),
                    "has_text_layer": bool(text.strip()),
                }
            )
    return {"source_checksum": checksum, "page_count": len(pages), "pages": pages}


def main() -> int:
    parser = argparse.ArgumentParser(description="Private PDF sayfa envanteri")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = inventory(args.input, args.source_root)
    except PdfSafetyError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
