"""Yetkili yerel PDF'den içeriksiz, private Gold benchmark manifesti hazırlar."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .pdf_text_layer import PdfSafetyError, _read_and_validate

KINDS = {"text", "formula", "table", "chart", "mixed", "exercise"}


def parse_item(value: str) -> dict:
    try:
        kind, page_text = value.split(":", maxsplit=1)
        page = int(page_text)
    except ValueError as exc:
        raise ValueError("Örnek biçimi kind:page olmalı; örnek formula:22") from exc
    if kind not in KINDS or page < 1:
        raise ValueError(f"Geçersiz Gold örneği: {value}")
    return {"id": f"{kind}-p{page}", "page": page, "kind": kind, "expected": ""}


def main() -> int:
    parser = argparse.ArgumentParser(description="Private Gold manifest hazırlar")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--item", action="append", required=True, help="kind:page; tekrar edilebilir"
    )
    args = parser.parse_args()
    try:
        _, content = _read_and_validate(args.input, args.source_root)
        items = [parse_item(item) for item in args.item]
    except (PdfSafetyError, ValueError) as exc:
        parser.error(str(exc))
    manifest = {
        "version": "gold-v1",
        "source_checksum": hashlib.sha256(content).hexdigest(),
        "annotation_state": "needs_human_gold_annotations",
        "items": items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
