"""Derive non-semantic grid-cell geometry from conservative vector grid candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path

import pymupdf

from .pdf_text_layer import MAX_PAGES, PdfSafetyError, SourceCoordinate, _read_and_validate
from .pdf_vector_structure import COORDINATE_TOLERANCE, _grid_candidates, _line_runs, _merge_runs


@dataclass(frozen=True)
class GridCellCandidate:
    id: str
    grid_id: str
    row: int
    column: int
    source: SourceCoordinate
    publication_status: str = "requires-schema-validation-and-review"


@dataclass(frozen=True)
class GridGeometryDocument:
    source_checksum: str
    page_count: int
    cells: list[GridCellCandidate]

    def to_dict(self) -> dict:
        return asdict(self)


def _coordinates(runs, orientation: str, minimum: float, maximum: float) -> list[float]:
    coordinates = sorted(
        run.coordinate
        for run in runs
        if run.orientation == orientation and minimum - COORDINATE_TOLERANCE <= run.coordinate <= maximum + COORDINATE_TOLERANCE
    )
    unique = []
    for coordinate in coordinates:
        if not unique or coordinate - unique[-1] > COORDINATE_TOLERANCE:
            unique.append(coordinate)
    return unique


def extract_grid_geometry(
    path: Path, source_root: Path, selected_pages: set[int] | None = None
) -> GridGeometryDocument:
    """Return source-linked cell geometry candidates, never cell values or relationships."""
    _, content = _read_and_validate(path, source_root)
    checksum = hashlib.sha256(content).hexdigest()
    try:
        pdf = pymupdf.open(stream=content, filetype="pdf")
    except pymupdf.FileDataError as exc:
        raise PdfSafetyError("PDF ayrıştırılamadı") from exc
    with pdf:
        if pdf.is_encrypted:
            raise PdfSafetyError("Şifreli PDF ızgara geometrisi için işlenmez")
        page_count = pdf.page_count
        if page_count < 1 or page_count > MAX_PAGES:
            raise PdfSafetyError(f"PDF sayfa sayısı 1 ile {MAX_PAGES} arasında olmalı")
        if selected_pages and (min(selected_pages) < 1 or max(selected_pages) > page_count):
            raise PdfSafetyError("Seçili sayfa PDF sayfa sınırlarının dışında")
        cells = []
        for page_number, page in enumerate(pdf, start=1):
            if selected_pages and page_number not in selected_pages:
                continue
            runs = _merge_runs(_line_runs(page))
            for grid_index, (bbox, _) in enumerate(_grid_candidates(runs), start=1):
                x0, y0, x1, y1 = bbox
                columns = _coordinates(runs, "vertical", x0, x1)
                rows = _coordinates(runs, "horizontal", y0, y1)
                if len(columns) < 2 or len(rows) < 2:
                    continue
                grid_id = f"p{page_number}-grid-{grid_index}"
                for row, (top, bottom) in enumerate(pairwise(rows), start=1):
                    for column, (left, right) in enumerate(pairwise(columns), start=1):
                        cells.append(
                            GridCellCandidate(
                                id=f"{grid_id}-r{row}-c{column}",
                                grid_id=grid_id,
                                row=row,
                                column=column,
                                source=SourceCoordinate(
                                    page=page_number,
                                    bbox=tuple(round(value, 2) for value in (left, top, right, bottom)),
                                    source_checksum=checksum,
                                    extraction_step="pdf-vector-grid-geometry",
                                ),
                            )
                        )
    return GridGeometryDocument(checksum, page_count, cells)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private PDF vector grid-cell geometry")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--pages", type=int, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = extract_grid_geometry(args.input, args.source_root, set(args.pages or []))
    except PdfSafetyError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
