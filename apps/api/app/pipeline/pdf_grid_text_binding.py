"""Conservative source-text binding for non-semantic vector grid cells.

Only a native PDF text block whose centre lies in exactly one cell and whose
intersection covers enough of the block is bound. This avoids guessing how a
spanning or ambiguous block should be split between table cells.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .pdf_text_layer import ExtractedBlock, PdfSafetyError, extract_text_layer
from .pdf_vector_grid import GridCellCandidate, extract_grid_geometry

MIN_BLOCK_COVERAGE = 0.8
MIN_BOUND_CELL_RATIO_FOR_TABLE_CANDIDATE = 0.5


@dataclass(frozen=True)
class BoundGridCellDraft:
    cell: GridCellCandidate
    block_ids: list[str]
    text: str
    binding_status: str
    publication_status: str = "requires-schema-validation-and-review"


@dataclass(frozen=True)
class GridBindingSummary:
    grid_id: str
    cell_count: int
    bound_cell_count: int
    bound_cell_ratio: float
    route: str


@dataclass(frozen=True)
class GridTextBindingDocument:
    source_checksum: str
    cells: list[BoundGridCellDraft]
    summaries: list[GridBindingSummary]

    def to_dict(self) -> dict:
        return asdict(self)


def _intersection_area(
    left: tuple[float, float, float, float], right: tuple[float, float, float, float]
) -> float:
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _contains_centre(cell: GridCellCandidate, block: ExtractedBlock) -> bool:
    x0, y0, x1, y1 = block.source.bbox
    centre_x, centre_y = (x0 + x1) / 2, (y0 + y1) / 2
    left, top, right, bottom = cell.source.bbox
    return left <= centre_x <= right and top <= centre_y <= bottom


def _eligible_cells(cells: list[GridCellCandidate], block: ExtractedBlock) -> list[GridCellCandidate]:
    block_area = (block.source.bbox[2] - block.source.bbox[0]) * (block.source.bbox[3] - block.source.bbox[1])
    if block_area <= 0:
        return []
    return [
        cell
        for cell in cells
        if cell.source.page == block.source.page
        and _contains_centre(cell, block)
        and _intersection_area(cell.source.bbox, block.source.bbox) / block_area >= MIN_BLOCK_COVERAGE
    ]


def bind_grid_text(
    path: Path, source_root: Path, selected_pages: set[int] | None = None
) -> GridTextBindingDocument:
    """Bind unambiguous native text blocks to grid cells; leave the rest unbound."""
    grid = extract_grid_geometry(path, source_root, selected_pages)
    extracted = extract_text_layer(path, source_root, selected_pages)
    if grid.source_checksum != extracted.source_checksum:
        raise PdfSafetyError("Vektör ve metin çıkarımı kaynak checksum'ında uyuşmuyor")
    bindings: dict[str, list[ExtractedBlock]] = {cell.id: [] for cell in grid.cells}
    for block in extracted.blocks:
        candidates = _eligible_cells(grid.cells, block)
        if len(candidates) == 1:
            bindings[candidates[0].id].append(block)
    drafts = []
    for cell in grid.cells:
        blocks = sorted(bindings[cell.id], key=lambda block: block.reading_order)
        drafts.append(
            BoundGridCellDraft(
                cell=cell,
                block_ids=[block.id for block in blocks],
                text=" ".join(block.text for block in blocks),
                binding_status="bound-native-text" if blocks else "unbound-needs-fallback-or-review",
            )
        )
    summaries = []
    for grid_id in sorted({cell.grid_id for cell in grid.cells}):
        grid_cells = [cell for cell in drafts if cell.cell.grid_id == grid_id]
        bound_count = sum(cell.binding_status == "bound-native-text" for cell in grid_cells)
        ratio = bound_count / len(grid_cells) if grid_cells else 0.0
        summaries.append(
            GridBindingSummary(
                grid_id=grid_id,
                cell_count=len(grid_cells),
                bound_cell_count=bound_count,
                bound_cell_ratio=round(ratio, 3),
                route=(
                    "candidate-table-schema-validation"
                    if ratio >= MIN_BOUND_CELL_RATIO_FOR_TABLE_CANDIDATE
                    else "insufficient-bound-text-needs-chart-or-visual-route"
                ),
            )
        )
    return GridTextBindingDocument(grid.source_checksum, drafts, summaries)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private PDF grid-to-text binding")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--pages", type=int, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = bind_grid_text(args.input, args.source_root, set(args.pages or []))
    except PdfSafetyError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
