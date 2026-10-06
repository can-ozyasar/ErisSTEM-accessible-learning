"""Render only routed embedded-image regions for private visual-model benchmarks."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

from .pdf_structure_routing import ExtractionRoute, build_structure_routing_plan
from .pdf_text_layer import PdfSafetyError, _read_and_validate

RENDER_SCALE = 2
MAX_RENDERED_PIXELS = 16_000_000


@dataclass(frozen=True)
class VisualRegionAsset:
    route_id: str
    candidate: str
    source: dict
    asset_path: str
    asset_checksum: str
    pixel_size: tuple[int, int]


@dataclass(frozen=True)
class VisualRegionManifest:
    source_checksum: str
    assets: list[VisualRegionAsset]

    def to_dict(self) -> dict:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render_route(page: pymupdf.Page, route: ExtractionRoute, output_dir: Path) -> VisualRegionAsset:
    clip = pymupdf.Rect(route.source.bbox) & page.rect
    if clip.is_empty or clip.width <= 0 or clip.height <= 0:
        raise PdfSafetyError("Görsel bölge PDF sayfa sınırlarının dışında")
    matrix = pymupdf.Matrix(RENDER_SCALE, RENDER_SCALE)
    pixel_width, pixel_height = round(clip.width * RENDER_SCALE), round(clip.height * RENDER_SCALE)
    if pixel_width * pixel_height > MAX_RENDERED_PIXELS:
        raise PdfSafetyError("Görsel bölge güvenli render piksel sınırını aşıyor")
    output_path = output_dir / f"{route.id}.png"
    page.get_pixmap(matrix=matrix, clip=clip, alpha=False).save(output_path)
    return VisualRegionAsset(
        route_id=route.id,
        candidate=route.candidate,
        source=asdict(route.source),
        asset_path=output_path.name,
        asset_checksum=_sha256(output_path),
        pixel_size=(pixel_width, pixel_height),
    )


def render_visual_regions(
    path: Path, source_root: Path, output_dir: Path, selected_pages: set[int] | None = None
) -> VisualRegionManifest:
    """Render only visual-model routes; never export a complete authorised PDF page."""
    safe_path, content = _read_and_validate(path, source_root)
    source_checksum = hashlib.sha256(content).hexdigest()
    plan = build_structure_routing_plan(safe_path, source_root, selected_pages)
    if source_checksum != plan.source_checksum:
        raise PdfSafetyError("Yönlendirme planı kaynak checksum'ında uyuşmuyor")
    output_dir.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        assets = [
            _render_route(pdf[route.source.page - 1], route, output_dir)
            for route in plan.routes
            if route.route == "visual-model-benchmark"
        ]
    return VisualRegionManifest(source_checksum, assets)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private PDF visual-region renderer")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--pages", type=int, nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = render_visual_regions(
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
