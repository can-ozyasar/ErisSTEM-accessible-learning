"""Private PDF vector/image evidence inventory with source coordinates.

This is a routing aid, not chart or table recognition. It never invents
semantic data from lines, images, or drawing commands. Downstream extraction
can prefer vector geometry when it exists, otherwise route the region to a
benchmark-approved visual model and teacher review policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

from .pdf_text_layer import MAX_PAGES, PdfSafetyError, SourceCoordinate, _read_and_validate


@dataclass(frozen=True)
class VectorRegion:
    id: str
    kind: str
    complexity: int
    source: SourceCoordinate


@dataclass(frozen=True)
class PageVectorEvidence:
    page: int
    page_size: tuple[float, float]
    drawing_count: int
    drawing_command_count: int
    embedded_image_count: int
    text_block_count: int
    route: str
    regions: list[VectorRegion]


@dataclass(frozen=True)
class VectorEvidenceDocument:
    source_checksum: str
    page_count: int
    pages: list[PageVectorEvidence]

    def to_dict(self) -> dict:
        return asdict(self)


def _bbox(rect: pymupdf.Rect) -> tuple[float, float, float, float] | None:
    if rect.is_empty or rect.width <= 0 or rect.height <= 0:
        return None
    return tuple(round(value, 2) for value in (rect.x0, rect.y0, rect.x1, rect.y1))


def _route(drawings: int, images: int) -> str:
    if drawings:
        return "vector-geometry-available"
    if images:
        return "embedded-image-needs-visual-extraction"
    return "no-nontext-object-evidence"


def extract_vector_evidence(
    path: Path, source_root: Path, selected_pages: set[int] | None = None
) -> VectorEvidenceDocument:
    """Extract only page geometry/image evidence from an authorised local PDF."""
    _, content = _read_and_validate(path, source_root)
    checksum = hashlib.sha256(content).hexdigest()
    try:
        pdf = pymupdf.open(stream=content, filetype="pdf")
    except pymupdf.FileDataError as exc:
        raise PdfSafetyError("PDF ayrıştırılamadı") from exc

    with pdf:
        if pdf.is_encrypted:
            raise PdfSafetyError("Şifreli PDF vektör kanıtı için işlenmez")
        page_count = pdf.page_count
        if page_count < 1 or page_count > MAX_PAGES:
            raise PdfSafetyError(f"PDF sayfa sayısı 1 ile {MAX_PAGES} arasında olmalı")
        if selected_pages and (min(selected_pages) < 1 or max(selected_pages) > page_count):
            raise PdfSafetyError("Seçili sayfa PDF sayfa sınırlarının dışında")

        evidence_pages = []
        for page_number, page in enumerate(pdf, start=1):
            if selected_pages and page_number not in selected_pages:
                continue
            drawings = page.get_drawings()
            image_regions = []
            seen_image_rects: set[tuple[float, float, float, float]] = set()
            for image in page.get_images(full=True):
                for rect in page.get_image_rects(image[0]):
                    bbox = _bbox(rect)
                    if bbox and bbox not in seen_image_rects:
                        seen_image_rects.add(bbox)
                        image_regions.append(bbox)

            regions: list[VectorRegion] = []
            for index, drawing in enumerate(drawings, start=1):
                bbox = _bbox(drawing["rect"])
                if not bbox:
                    continue
                regions.append(
                    VectorRegion(
                        id=f"p{page_number}-vector-{index}",
                        kind="vector-drawing",
                        complexity=len(drawing.get("items", [])),
                        source=SourceCoordinate(
                            page=page_number,
                            bbox=bbox,
                            source_checksum=checksum,
                            extraction_step="pdf-vector-evidence",
                        ),
                    )
                )
            for index, bbox in enumerate(image_regions, start=1):
                regions.append(
                    VectorRegion(
                        id=f"p{page_number}-image-{index}",
                        kind="embedded-image",
                        complexity=0,
                        source=SourceCoordinate(
                            page=page_number,
                            bbox=bbox,
                            source_checksum=checksum,
                            extraction_step="pdf-vector-evidence",
                        ),
                    )
                )
            evidence_pages.append(
                PageVectorEvidence(
                    page=page_number,
                    page_size=(round(page.rect.width, 2), round(page.rect.height, 2)),
                    drawing_count=len(drawings),
                    drawing_command_count=sum(len(drawing.get("items", [])) for drawing in drawings),
                    embedded_image_count=len(image_regions),
                    text_block_count=len(page.get_text("blocks", sort=True)),
                    route=_route(len(drawings), len(image_regions)),
                    regions=regions,
                )
            )
    return VectorEvidenceDocument(checksum, page_count, evidence_pages)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private PDF vector/image evidence inventory")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--pages", type=int, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = extract_vector_evidence(args.input, args.source_root, set(args.pages or []))
    except PdfSafetyError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
