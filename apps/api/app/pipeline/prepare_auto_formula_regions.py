"""Prepare source-bound whole-expression crops from pending PDF math fragments."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

from ..job_store import DocumentStore, make_session_factory
from .materialize import looks_like_fragmented_math
from .pdf_text_layer import _read_and_validate

SCHEMA = "formula-region-benchmark-input-v1"
BINDINGS_SCHEMA = "formula-ocr-bindings-v1"
RENDER_SCALE = 4
MARGIN = 4
ROW_CENTER_TOLERANCE = 12.0


def _candidate_blocks(document: dict) -> list[dict]:
    return [
        block for block in document["blocks"]
        if block["status"] == "review_required" and (
            # Never replace a whole-expression proposal that has already been
            # generated and inspected; only pending/raw fragments enter this
            # batch.
            (block["kind"] == "formula-display" and not str(block["source"].get("extraction_step", "")).startswith("formula-ocr:"))
            or looks_like_fragmented_math(block.get("text") or "")
        )
    ]


def _row_groups(blocks: list[dict]) -> list[list[dict]]:
    """Merge source fragments on one visual baseline, never adjacent rows."""
    per_page: dict[int, list[dict]] = {}
    for block in blocks:
        per_page.setdefault(int(block["source"]["page"]), []).append(block)
    groups: list[list[dict]] = []
    for page, values in per_page.items():
        del page
        rows: list[tuple[float, list[dict]]] = []
        for block in sorted(values, key=lambda item: ((item["source"]["bbox"][1] + item["source"]["bbox"][3]) / 2, item["source"]["bbox"][0])):
            box = block["source"]["bbox"]
            center = (box[1] + box[3]) / 2
            if rows and abs(center - rows[-1][0]) <= ROW_CENTER_TOLERANCE:
                previous_center, row = rows[-1]
                row.append(block)
                rows[-1] = ((previous_center * (len(row) - 1) + center) / len(row), row)
            else:
                rows.append((center, [block]))
        groups.extend(row for _, row in rows)
    return groups


def _bbox(blocks: list[dict]) -> tuple[float, float, float, float]:
    boxes = [block["source"]["bbox"] for block in blocks]
    return min(box[0] for box in boxes), min(box[1] for box in boxes), max(box[2] for box in boxes), max(box[3] for box in boxes)


def prepare(document: dict, source_pdf: Path, source_root: Path, output_dir: Path) -> tuple[dict, dict]:
    """Render all pending formula rows and save separate source-block bindings."""
    _, content = _read_and_validate(source_pdf, source_root)
    checksum = hashlib.sha256(content).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    images = output_dir / "images"
    images.mkdir(exist_ok=True)
    regions, bindings = [], []
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        for index, row in enumerate(_row_groups(_candidate_blocks(document)), start=1):
            page_number = int(row[0]["source"]["page"])
            if any(int(block["source"]["page"]) != page_number for block in row):
                raise ValueError("formula_row_crosses_pages")
            left, top, right, bottom = _bbox(row)
            page = pdf[page_number - 1]
            clip = pymupdf.Rect(left, top, right, bottom) + (-MARGIN, -MARGIN, MARGIN, MARGIN)
            clip = clip & page.rect
            if clip.is_empty:
                raise ValueError("formula_crop_outside_page")
            region_id = f"auto-p{page_number}-{index}"
            image_path = images / f"{region_id}.png"
            image_path.write_bytes(page.get_pixmap(matrix=pymupdf.Matrix(RENDER_SCALE, RENDER_SCALE), clip=clip, alpha=False).tobytes("png"))
            regions.append({
                "id": region_id, "asset_path": str(image_path.relative_to(output_dir)),
                "asset_checksum": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "source_checksum": checksum, "page": page_number, "bbox": [left, top, right, bottom],
            })
            bindings.append({"region_id": region_id, "block_ids": [block["id"] for block in sorted(row, key=lambda item: item["reading_order"])]})
    manifest = {"schema_version": SCHEMA, "regions": regions}
    binding_manifest = {"schema_version": BINDINGS_SCHEMA, "document_id": document["id"], "bindings": bindings}
    (output_dir / "formula-region-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "formula-ocr-bindings.json").write_text(json.dumps(binding_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest, binding_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare automatic whole-formula OCR regions")
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    document = DocumentStore(make_session_factory()).get(args.document_id)
    if document is None:
        parser.error("document_not_found")
    manifest, bindings = prepare(document, args.input, args.source_root, args.output_dir)
    print(json.dumps({"regions": len(manifest["regions"]), "bindings": len(bindings["bindings"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
