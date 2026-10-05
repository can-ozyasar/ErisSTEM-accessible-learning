"""Yerel, yetkili PDF metin-katmanı worker komutu."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pdf_text_layer import PdfSafetyError, extract_text_layer


def write_text_layer(result, output_dir: Path) -> Path:
    """Ara çıktıyı atomik olarak özel türetilmiş veri dizinine yazar."""
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{result.source_checksum}.text-layer.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="ErişSTEM PDF metin katmanı çıkarıcısı")
    parser.add_argument("--input", type=Path, required=True, help="data/meb altındaki PDF")
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/derived"))
    args = parser.parse_args()
    try:
        result = extract_text_layer(args.input, args.source_root)
    except PdfSafetyError as exc:
        parser.error(str(exc))
    print(write_text_layer(result, args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
