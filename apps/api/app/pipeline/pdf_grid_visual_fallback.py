"""Render merged low-binding vector-grid regions for private visual fallback.

This is used when the PDF contains table-like vector geometry but its native
text layer cannot be safely assigned to cells. It remains a benchmark input,
never a semantic table result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

from .pdf_grid_text_binding import bind_grid_text
from .pdf_text_layer import PdfSafetyError, SourceCoordinate, _read_and_validate
from .pdf_vector_structure import extract_vector_structure
from .pdf_visual_regions import MAX_RENDERED_PIXELS, RENDER_SCALE, _sha256

MAX_HORIZONTAL_JOIN_GAP = 36.0
MIN_VERTICAL_OVERLAP_RATIO = 0.8


@dataclass(frozen=True)
class GridVisualAsset:
    route_id: str
    candidate: str
    source: SourceCoordinate
    asset_path: str
    asset_checksum: str
    pixel_size: tuple[int, int]


@dataclass(frozen=True)
class GridVisualManifest:
    source_checksum: str
    assets: list[GridVisualAsset]

    def to_dict(self) -> dict:
        return asdict(self)


def _vertical_overlap_ratio(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> float:
    overlap = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    return overlap / min(left[3] - left[1], right[3] - right[1])


def _merge_bboxes(bboxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )


def _merged_grid_regions(path: Path, source_root: Path, selected_pages: set[int] | None) -> list[SourceCoordinate]:
    structure = extract_vector_structure(path, source_root, selected_pages)
    binding = bind_grid_text(path, source_root, selected_pages)
    summaries = {summary.grid_id: summary for summary in binding.summaries}
    candidates = [
        candidate
        for candidate in structure.candidates
        if candidate.kind == "rectilinear-grid-candidate"
        and summaries.get(candidate.id)
        and summaries[candidate.id].route == "insufficient-bound-text-needs-chart-or-visual-route"
    ]
    by_page: dict[int, list[SourceCoordinate]] = {}
    for candidate in candidates:
        by_page.setdefault(candidate.source.page, []).append(candidate.source)
    regions = []
    for page, sources in by_page.items():
        groups: list[list[SourceCoordinate]] = []
        for source in sorted(sources, key=lambda item: item.bbox[0]):
            if not groups:
                groups.append([source])
                continue
            current = groups[-1]
            current_bbox = _merge_bboxes([item.bbox for item in current])
            gap = source.bbox[0] - current_bbox[2]
            if gap <= MAX_HORIZONTAL_JOIN_GAP and _vertical_overlap_ratio(current_bbox, source.bbox) >= MIN_VERTICAL_OVERLAP_RATIO:
                current.append(source)
            else:
                groups.append([source])
        for group in groups:
            bbox = tuple(round(value, 2) for value in _merge_bboxes([item.bbox for item in group]))
            regions.append(
                SourceCoordinate(
                    page=page,
                    bbox=bbox,
                    source_checksum=structure.source_checksum,
                    extraction_step="pdf-grid-visual-fallback",
                )
            )
    return regions


def render_grid_visual_fallback(
    path: Path, source_root: Path, output_dir: Path, selected_pages: set[int] | None = None
) -> GridVisualManifest:
    """Render only merged insufficient-binding grid regions as private crops."""
    _, content = _read_and_validate(path, source_root)
    checksum = hashlib.sha256(content).hexdigest()
    regions = _merged_grid_regions(path, source_root, selected_pages)
    if any(region.source_checksum != checksum for region in regions):
        raise PdfSafetyError("Izgara fallback kaynağı checksum ile uyuşmuyor")
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = []
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        for index, source in enumerate(regions, start=1):
            clip = pymupdf.Rect(source.bbox) & pdf[source.page - 1].rect
            width, height = round(clip.width * RENDER_SCALE), round(clip.height * RENDER_SCALE)
            if clip.is_empty or width * height > MAX_RENDERED_PIXELS:
                raise PdfSafetyError("Izgara fallback bölgesi güvenli render sınırını aşıyor")
            route_id = f"p{source.page}-grid-visual-{index}"
            output_path = output_dir / f"{route_id}.png"
            pdf[source.page - 1].get_pixmap(
                matrix=pymupdf.Matrix(RENDER_SCALE, RENDER_SCALE), clip=clip, alpha=False
            ).save(output_path)
            assets.append(
                GridVisualAsset(
                    route_id=route_id,
                    candidate="paddleocr-vl-or-approved-fallback",
                    source=source,
                    asset_path=output_path.name,
                    asset_checksum=_sha256(output_path),
                    pixel_size=(width, height),
                )
            )
    return GridVisualManifest(checksum, assets)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private PDF grid visual fallback renderer")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--pages", type=int, nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = render_grid_visual_fallback(
            args.input, args.source_root, args.output_dir, set(args.pages or [])
        )
    except PdfSafetyError as exc:
        parser.error(str(exc))
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
