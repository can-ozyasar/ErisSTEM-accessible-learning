"""Private vector-grid plus native-word table candidates for preselected regions.

This deterministic fallback is deliberately limited to checksum-bound private
regions. It does not infer merged cells or publish material; ambiguous regions
remain blocked for Gold/teacher review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path

import pymupdf

from .pdf_text_layer import PdfSafetyError, SourceCoordinate, _read_and_validate
from .pdf_vector_structure import COORDINATE_TOLERANCE, _line_runs, _merge_runs
from .visual_result_schema import VisualTableDraft

MIN_AXIS_COVERAGE = 0.5


@dataclass(frozen=True)
class RegionVectorTableResult:
    region_id: str
    status: str
    draft: dict | None
    grid_rows: int
    grid_columns: int
    bound_word_count: int


def _manifest_regions(path: Path) -> list[tuple[str, SourceCoordinate]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list) or not assets:
        raise PdfSafetyError("Görsel bölge manifestinde asset bulunamadı")
    regions = []
    for asset in assets:
        source = asset.get("source") if isinstance(asset, dict) else None
        bbox = source.get("bbox") if isinstance(source, dict) else None
        if (
            not isinstance(asset.get("route_id") if isinstance(asset, dict) else None, str)
            or not isinstance(source.get("page") if isinstance(source, dict) else None, int)
            or not isinstance(bbox, list)
            or len(bbox) != 4
            or not all(isinstance(value, int | float) for value in bbox)
            or not isinstance(source.get("source_checksum") if isinstance(source, dict) else None, str)
        ):
            raise PdfSafetyError("Görsel bölge kaynak şeması geçersiz")
        regions.append(
            (
                asset["route_id"],
                SourceCoordinate(
                    page=source["page"],
                    bbox=tuple(float(value) for value in bbox),
                    source_checksum=source["source_checksum"],
                    extraction_step="pdf-region-vector-table",
                ),
            )
        )
    return regions


def _merged_coverage(intervals: list[tuple[float, float]]) -> float:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + COORDINATE_TOLERANCE:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return sum(end - start for start, end in merged)


def _axis_positions(runs, orientation: str, bbox: tuple[float, float, float, float]) -> list[float]:
    x0, y0, x1, y1 = bbox
    coordinate_minimum, coordinate_maximum = (x0, x1) if orientation == "vertical" else (y0, y1)
    span_minimum, span_maximum = (y0, y1) if orientation == "vertical" else (x0, x1)
    grouped: dict[float, list[tuple[float, float]]] = defaultdict(list)
    for run in runs:
        if run.orientation != orientation or not (coordinate_minimum - COORDINATE_TOLERANCE <= run.coordinate <= coordinate_maximum + COORDINATE_TOLERANCE):
            continue
        start, end = max(run.start, span_minimum), min(run.end, span_maximum)
        if end > start:
            grouped[round(run.coordinate, 2)].append((start, end))
    minimum_coverage = (span_maximum - span_minimum) * MIN_AXIS_COVERAGE
    positions = [coordinate for coordinate, intervals in grouped.items() if _merged_coverage(intervals) >= minimum_coverage]
    return sorted(positions)


def _word_cell_values(page: pymupdf.Page, cells: list[tuple[int, int, tuple[float, float, float, float]]]) -> tuple[dict[tuple[int, int], str], int]:
    values: dict[tuple[int, int], list[tuple[float, float, str]]] = defaultdict(list)
    union = pymupdf.Rect(
        min(cell[2][0] for cell in cells), min(cell[2][1] for cell in cells), max(cell[2][2] for cell in cells), max(cell[2][3] for cell in cells)
    )
    for x0, y0, x1, y1, text, *_ in page.get_text("words", clip=union, sort=True):
        centre_x, centre_y = (x0 + x1) / 2, (y0 + y1) / 2
        matches = [
            (row, column)
            for row, column, (left, top, right, bottom) in cells
            if left <= centre_x <= right and top <= centre_y <= bottom
        ]
        if len(matches) == 1:
            values[matches[0]].append((y0, x0, text))
    return {
        key: " ".join(text for _, _, text in sorted(words))
        for key, words in values.items()
    }, sum(len(words) for words in values.values())


def extract_region_vector_tables(path: Path, source_root: Path, regions_manifest: Path) -> list[RegionVectorTableResult]:
    """Create strict, low-confidence table drafts from vector axes and native words."""
    _, content = _read_and_validate(path, source_root)
    checksum = hashlib.sha256(content).hexdigest()
    regions = _manifest_regions(regions_manifest)
    results = []
    with pymupdf.open(stream=content, filetype="pdf") as document:
        for region_id, source in regions:
            if source.source_checksum != checksum or not 1 <= source.page <= document.page_count:
                results.append(RegionVectorTableResult(region_id, "blocked-source-mismatch", None, 0, 0, 0))
                continue
            page = document[source.page - 1]
            runs = _merge_runs(_line_runs(page))
            columns = _axis_positions(runs, "vertical", source.bbox)
            rows = _axis_positions(runs, "horizontal", source.bbox)
            if len(columns) < 2 or len(rows) < 2:
                results.append(RegionVectorTableResult(region_id, "blocked-insufficient-vector-grid", None, 0, 0, 0))
                continue
            cells = [
                (row, column, (left, top, right, bottom))
                for row, (top, bottom) in enumerate(pairwise(rows), start=1)
                for column, (left, right) in enumerate(pairwise(columns), start=1)
            ]
            values, word_count = _word_cell_values(page, cells)
            payload = {
                "kind": "table",
                "source": {
                    "region_id": region_id,
                    "source_checksum": checksum,
                    "page": source.page,
                    "bbox": source.bbox,
                },
                "cells": [
                    {
                        "row": row,
                        "column": column,
                        "role": "header" if row == 1 else "data",
                        "text": values.get((row, column), ""),
                        "confidence": 0.0,
                    }
                    for row, column, _ in cells
                ],
                "confidence": 0.0,
            }
            draft = VisualTableDraft.model_validate(payload).model_dump(mode="json")
            results.append(
                RegionVectorTableResult(
                    region_id,
                    "candidate-vector-native-needs-gold-and-review",
                    {"schema_version": "visual-table-draft-v1", **draft, "publication_status": "requires-gold-and-teacher-review"},
                    len(rows) - 1,
                    len(columns) - 1,
                    word_count,
                )
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Private vector/native table extraction for selected regions")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--regions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract_region_vector_tables(args.input, args.source_root, args.regions)
    args.output.write_text(json.dumps([asdict(item) for item in result], ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0
