"""Render selected source PDF pages for visual formula-layout evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

from .pdf_text_layer import _read_and_validate


def prepare(source_pdf: Path, source_root: Path, pages: list[int], output_dir: Path) -> dict:
    _, content = _read_and_validate(source_pdf, source_root)
    checksum = hashlib.sha256(content).hexdigest()
    if not pages or len(set(pages)) != len(pages):
        raise ValueError("pages_must_be_unique")
    images = output_dir / "pages"
    images.mkdir(parents=True, exist_ok=True)
    records = []
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        for number in pages:
            if not 1 <= number <= pdf.page_count:
                raise ValueError("page_outside_source")
            path = images / f"page-{number}.png"
            path.write_bytes(pdf[number - 1].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).tobytes("png"))
            records.append({"page": number, "asset_path": str(path.relative_to(output_dir)), "asset_checksum": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {"schema_version": "formula-layout-probe-v1", "source_checksum": checksum, "pages": records}
    (output_dir / "page-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Render whole PDF pages for visual formula-layout probe")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pages", required=True, help="comma-separated 1-based page numbers")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    pages = [int(item) for item in args.pages.split(",")]
    manifest = prepare(args.input, args.source_root, pages, args.output_dir)
    print(json.dumps({"pages": len(manifest["pages"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
