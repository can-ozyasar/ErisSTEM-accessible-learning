"""Prepare private, source-bound mathematical-symbol cell benchmark assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import pairwise
from pathlib import Path

import pymupdf

from .pdf_region_vector_table import _axis_positions
from .pdf_text_layer import PdfSafetyError, _read_and_validate
from .pdf_vector_structure import _line_runs, _merge_runs
from .visual_table_benchmark import VisualTableGoldManifest, _symbol_critical_cell

INPUT_SCHEMA = "symbol-cell-benchmark-input-v1"
GOLD_SCHEMA = "symbol-cell-gold-v1"
RENDER_SCALE = 4


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_id(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else "-" for character in value)


def prepare_symbol_cell_benchmark(
    source_pdf: Path,
    source_root: Path,
    gold_path: Path,
    output_dir: Path,
    gold_output: Path,
) -> tuple[dict, dict]:
    """Render Gold-designated symbol cells while storing answers outside candidate input."""
    _, content = _read_and_validate(source_pdf, source_root)
    checksum = hashlib.sha256(content).hexdigest()
    gold = VisualTableGoldManifest.model_validate_json(gold_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    images = output_dir / "images"
    images.mkdir(exist_ok=True)
    assets, expected = [], []
    with pymupdf.open(stream=content, filetype="pdf") as document:
        for table in gold.tables:
            source = table.source
            if source.source_checksum != checksum or not 1 <= source.page <= document.page_count:
                raise PdfSafetyError("Gold tablo kaynağı private PDF ile eşleşmiyor")
            page = document[source.page - 1]
            runs = _merge_runs(_line_runs(page))
            columns = _axis_positions(runs, "vertical", source.bbox)
            rows = _axis_positions(runs, "horizontal", source.bbox)
            if len(columns) < 2 or len(rows) < 2:
                raise PdfSafetyError("Gold tablo için vektör hücre geometrisi bulunamadı")
            geometry = {
                (row, column): (left, top, right, bottom)
                for row, (top, bottom) in enumerate(pairwise(rows), start=1)
                for column, (left, right) in enumerate(pairwise(columns), start=1)
            }
            for cell in table.cells:
                if not _symbol_critical_cell(cell.text):
                    continue
                bbox = geometry.get((cell.row, cell.column))
                if bbox is None:
                    raise PdfSafetyError("Gold hücresi kaynak ızgara geometrisiyle eşleşmiyor")
                asset_id = _safe_id(f"{source.region_id}-r{cell.row}-c{cell.column}")
                image_path = images / f"{asset_id}.png"
                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(RENDER_SCALE, RENDER_SCALE), clip=pymupdf.Rect(bbox), alpha=False
                )
                image_path.write_bytes(pixmap.tobytes("png"))
                assets.append(
                    {
                        "id": asset_id,
                        "asset_path": str(image_path.relative_to(output_dir)),
                        "asset_checksum": sha256(image_path),
                        "source": source.model_dump(mode="json"),
                        "cell": {"row": cell.row, "column": cell.column, "bbox": bbox},
                    }
                )
                expected.append({"id": asset_id, "expected": cell.text})
    input_manifest = {"schema_version": INPUT_SCHEMA, "assets": assets}
    gold_manifest = {"schema_version": GOLD_SCHEMA, "expected": expected}
    (output_dir / "symbol-cell-manifest.json").write_text(
        json.dumps(input_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    gold_output.parent.mkdir(parents=True, exist_ok=True)
    gold_output.write_text(
        json.dumps(gold_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return input_manifest, gold_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare private mathematical-symbol cell benchmark")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--gold-output",
        type=Path,
        required=True,
        help="Private local expected-answer manifest; never include it in candidate input.",
    )
    args = parser.parse_args()
    try:
        inputs, gold = prepare_symbol_cell_benchmark(
            args.input, args.source_root, args.gold, args.output_dir, args.gold_output
        )
    except (OSError, ValueError, PdfSafetyError) as exc:
        parser.error(str(exc))
    print(json.dumps({"prepared_symbol_cells": len(inputs["assets"]), "gold_cells": len(gold["expected"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
