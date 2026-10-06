"""Öğretmen denetimi için private PDF sayfa önizlemeleri üretir."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pymupdf

from .pdf_text_layer import PdfSafetyError, _read_and_validate


def write_review_previews(
    path: Path, source_root: Path, output_dir: Path, document_id: str, pages: set[int]
) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{1,100}", document_id):
        raise PdfSafetyError("Belge kimliği güvenli biçimde oluşturulmamış")
    _, content = _read_and_validate(path, source_root)
    target = output_dir / "review-pages" / document_id
    target.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, dict[str, float]] = {}
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        if not pages or min(pages) < 1 or max(pages) > pdf.page_count:
            raise PdfSafetyError("Seçili sayfa PDF sayfa sınırlarının dışında")
        for page_number in sorted(pages):
            page = pdf[page_number - 1]
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            temporary = target / f"page-{page_number}.tmp"
            temporary.write_bytes(pixmap.tobytes("png"))
            temporary.replace(target / f"page-{page_number}.png")
            metadata[str(page_number)] = {"width": page.rect.width, "height": page.rect.height}
    (target / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Private öğretmen sayfa önizlemesi üretir")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/derived"))
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--pages", required=True)
    args = parser.parse_args()
    try:
        pages = {int(value) for value in args.pages.split(",")}
        print(
            write_review_previews(
                args.input, args.source_root, args.output_dir, args.document_id, pages
            )
        )
    except (PdfSafetyError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
