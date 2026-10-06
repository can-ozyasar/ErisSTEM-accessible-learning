"""Conservative table-grid and chart-axis candidates from PDF vector geometry.

This module recognises geometry only. A grid is not asserted to be a semantic
table and an axis pair is not asserted to be a semantic chart. Every candidate
keeps its source coordinate and is deliberately marked as a review/benchmark
candidate rather than publishable educational content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

from .pdf_text_layer import MAX_PAGES, PdfSafetyError, SourceCoordinate, _read_and_validate

COORDINATE_TOLERANCE = 2.0
MIN_LINE_LENGTH = 24.0
MIN_CANDIDATE_EXTENT = 48.0


@dataclass(frozen=True)
class LineRun:
    orientation: str
    coordinate: float
    start: float
    end: float

    @property
    def length(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class VectorStructureCandidate:
    id: str
    kind: str
    confidence: float
    evidence: dict[str, int]
    source: SourceCoordinate
    publication_status: str = "requires-benchmark-and-review"


@dataclass(frozen=True)
class VectorStructureDocument:
    source_checksum: str
    page_count: int
    candidates: list[VectorStructureCandidate]

    def to_dict(self) -> dict:
        return asdict(self)


def _round_bbox(values: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return tuple(round(value, 2) for value in values)


def _line_runs(page: pymupdf.Page) -> list[LineRun]:
    """Extract only long horizontal/vertical segments; curves are intentionally ignored."""
    runs = []
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if item[0] == "l":
                start, end = item[1], item[2]
                x0, y0, x1, y1 = start.x, start.y, end.x, end.y
                if abs(y1 - y0) <= COORDINATE_TOLERANCE and abs(x1 - x0) >= MIN_LINE_LENGTH:
                    runs.append(LineRun("horizontal", (y0 + y1) / 2, min(x0, x1), max(x0, x1)))
                if abs(x1 - x0) <= COORDINATE_TOLERANCE and abs(y1 - y0) >= MIN_LINE_LENGTH:
                    runs.append(LineRun("vertical", (x0 + x1) / 2, min(y0, y1), max(y0, y1)))
            elif item[0] == "re":
                rect = item[1]
                if rect.width >= MIN_LINE_LENGTH:
                    runs.extend(
                        (
                            LineRun("horizontal", rect.y0, rect.x0, rect.x1),
                            LineRun("horizontal", rect.y1, rect.x0, rect.x1),
                        )
                    )
                if rect.height >= MIN_LINE_LENGTH:
                    runs.extend(
                        (
                            LineRun("vertical", rect.x0, rect.y0, rect.y1),
                            LineRun("vertical", rect.x1, rect.y0, rect.y1),
                        )
                    )
    return runs


def _merge_runs(runs: list[LineRun]) -> list[LineRun]:
    """Merge collinear overlapping/adjacent segments without inventing connections."""
    grouped: dict[str, list[LineRun]] = defaultdict(list)
    for run in runs:
        grouped[run.orientation].append(run)
    merged = []
    for orientation, orientation_runs in grouped.items():
        coordinate_groups: list[list[LineRun]] = []
        for run in sorted(orientation_runs, key=lambda candidate: candidate.coordinate):
            if not coordinate_groups or abs(run.coordinate - coordinate_groups[-1][0].coordinate) > COORDINATE_TOLERANCE:
                coordinate_groups.append([run])
            else:
                coordinate_groups[-1].append(run)
        for group in coordinate_groups:
            coordinate = sum(run.coordinate for run in group) / len(group)
            spans: list[tuple[float, float]] = []
            for run in sorted(group, key=lambda candidate: candidate.start):
                if not spans or run.start > spans[-1][1] + COORDINATE_TOLERANCE:
                    spans.append((run.start, run.end))
                else:
                    spans[-1] = (spans[-1][0], max(spans[-1][1], run.end))
            merged.extend(LineRun(orientation, coordinate, start, end) for start, end in spans)
    return merged


def _intersects(horizontal: LineRun, vertical: LineRun) -> bool:
    return horizontal.start - COORDINATE_TOLERANCE <= vertical.coordinate <= horizontal.end + COORDINATE_TOLERANCE and (
        vertical.start - COORDINATE_TOLERANCE <= horizontal.coordinate <= vertical.end + COORDINATE_TOLERANCE
    )


def _grid_candidates(runs: list[LineRun]) -> list[tuple[tuple[float, float, float, float], dict[str, int]]]:
    horizontals = [run for run in runs if run.orientation == "horizontal"]
    verticals = [run for run in runs if run.orientation == "vertical"]
    horizontal_edges: dict[int, set[int]] = defaultdict(set)
    vertical_edges: dict[int, set[int]] = defaultdict(set)
    for horizontal_index, horizontal in enumerate(horizontals):
        for vertical_index, vertical in enumerate(verticals):
            if _intersects(horizontal, vertical):
                horizontal_edges[horizontal_index].add(vertical_index)
                vertical_edges[vertical_index].add(horizontal_index)
    candidates = []
    visited_horizontals: set[int] = set()
    visited_verticals: set[int] = set()
    for seed in horizontal_edges:
        if seed in visited_horizontals:
            continue
        component_horizontals = set()
        component_verticals = set()
        pending_horizontals = [seed]
        while pending_horizontals:
            horizontal_index = pending_horizontals.pop()
            if horizontal_index in component_horizontals:
                continue
            component_horizontals.add(horizontal_index)
            visited_horizontals.add(horizontal_index)
            for vertical_index in horizontal_edges[horizontal_index]:
                if vertical_index in component_verticals:
                    continue
                component_verticals.add(vertical_index)
                visited_verticals.add(vertical_index)
                pending_horizontals.extend(vertical_edges[vertical_index] - component_horizontals)
        related_h = [horizontals[index] for index in component_horizontals]
        related_v = [verticals[index] for index in component_verticals]
        edge_count = sum(len(horizontal_edges[index] & component_verticals) for index in component_horizontals)
        possible_edges = len(related_h) * len(related_v)
        # A sparse set of perpendicular decorations is not a table grid. This
        # is intentionally conservative; the threshold is benchmarked, not a
        # publication-confidence claim.
        if len(related_h) < 2 or len(related_v) < 2 or edge_count / possible_edges < 0.5:
            continue
        x0, x1 = min(run.coordinate for run in related_v), max(run.coordinate for run in related_v)
        y0, y1 = min(run.coordinate for run in related_h), max(run.coordinate for run in related_h)
        if x1 - x0 < MIN_CANDIDATE_EXTENT or y1 - y0 < MIN_CANDIDATE_EXTENT:
            continue
        candidates.append(
            (
                _round_bbox((x0, y0, x1, y1)),
                {
                    "horizontal_runs": len(related_h),
                    "vertical_runs": len(related_v),
                    "intersections": edge_count,
                },
            )
        )
    return sorted(candidates)


def _axis_candidates(runs: list[LineRun]) -> list[tuple[tuple[float, float, float, float], dict[str, int]]]:
    horizontals = [run for run in runs if run.orientation == "horizontal" and run.length >= MIN_CANDIDATE_EXTENT]
    verticals = [run for run in runs if run.orientation == "vertical" and run.length >= MIN_CANDIDATE_EXTENT]
    candidates = []
    for horizontal in horizontals:
        for vertical in verticals:
            if not _intersects(horizontal, vertical):
                continue
            is_horizontal_endpoint = min(
                abs(vertical.coordinate - horizontal.start), abs(vertical.coordinate - horizontal.end)
            ) <= COORDINATE_TOLERANCE
            is_vertical_endpoint = min(
                abs(horizontal.coordinate - vertical.start), abs(horizontal.coordinate - vertical.end)
            ) <= COORDINATE_TOLERANCE
            if not (is_horizontal_endpoint and is_vertical_endpoint):
                continue
            bbox = _round_bbox(
                (
                    min(horizontal.start, vertical.coordinate),
                    min(vertical.start, horizontal.coordinate),
                    max(horizontal.end, vertical.coordinate),
                    max(vertical.end, horizontal.coordinate),
                )
            )
            candidates.append((bbox, {"horizontal_length": round(horizontal.length), "vertical_length": round(vertical.length)}))
    unique = {}
    for bbox, evidence in candidates:
        unique[bbox] = evidence
    return sorted(unique.items())


def extract_vector_structure(
    path: Path, source_root: Path, selected_pages: set[int] | None = None
) -> VectorStructureDocument:
    """Produce conservative, source-linked geometry candidates from an authorised PDF."""
    _, content = _read_and_validate(path, source_root)
    checksum = hashlib.sha256(content).hexdigest()
    try:
        pdf = pymupdf.open(stream=content, filetype="pdf")
    except pymupdf.FileDataError as exc:
        raise PdfSafetyError("PDF ayrıştırılamadı") from exc
    with pdf:
        if pdf.is_encrypted:
            raise PdfSafetyError("Şifreli PDF vektör yapısı için işlenmez")
        page_count = pdf.page_count
        if page_count < 1 or page_count > MAX_PAGES:
            raise PdfSafetyError(f"PDF sayfa sayısı 1 ile {MAX_PAGES} arasında olmalı")
        if selected_pages and (min(selected_pages) < 1 or max(selected_pages) > page_count):
            raise PdfSafetyError("Seçili sayfa PDF sayfa sınırlarının dışında")
        candidates = []
        for page_number, page in enumerate(pdf, start=1):
            if selected_pages and page_number not in selected_pages:
                continue
            runs = _merge_runs(_line_runs(page))
            for index, (bbox, evidence) in enumerate(_grid_candidates(runs), start=1):
                density = min(evidence["horizontal_runs"], evidence["vertical_runs"])
                candidates.append(
                    VectorStructureCandidate(
                        id=f"p{page_number}-grid-{index}",
                        kind="rectilinear-grid-candidate",
                        confidence=round(min(0.9, 0.4 + density * 0.08), 2),
                        evidence=evidence,
                        source=SourceCoordinate(
                            page=page_number,
                            bbox=bbox,
                            source_checksum=checksum,
                            extraction_step="pdf-vector-structure",
                        ),
                    )
                )
            for index, (bbox, evidence) in enumerate(_axis_candidates(runs), start=1):
                candidates.append(
                    VectorStructureCandidate(
                        id=f"p{page_number}-axes-{index}",
                        kind="perpendicular-axis-candidate",
                        confidence=0.55,
                        evidence=evidence,
                        source=SourceCoordinate(
                            page=page_number,
                            bbox=bbox,
                            source_checksum=checksum,
                            extraction_step="pdf-vector-structure",
                        ),
                    )
                )
    return VectorStructureDocument(checksum, page_count, candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private PDF vector structure candidates")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--pages", type=int, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = extract_vector_structure(args.input, args.source_root, set(args.pages or []))
    except PdfSafetyError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
