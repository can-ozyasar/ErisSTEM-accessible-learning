"""Build a private, source-linked routing plan for vector and visual extraction.

Routing is deliberately not recognition: no table cells, chart values, OCR text,
or student-visible content is produced here. It makes the downstream candidate
and review requirement explicit for each source region.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .pdf_text_layer import PdfSafetyError, SourceCoordinate
from .pdf_vector_evidence import extract_vector_evidence
from .pdf_vector_structure import extract_vector_structure


@dataclass(frozen=True)
class ExtractionRoute:
    id: str
    route: str
    candidate: str
    source: SourceCoordinate
    review_required: bool = True


@dataclass(frozen=True)
class StructureRoutingPlan:
    source_checksum: str
    routes: list[ExtractionRoute]

    def to_dict(self) -> dict:
        return asdict(self)


def _overlaps(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> bool:
    return not (left[2] <= right[0] or right[2] <= left[0] or left[3] <= right[1] or right[3] <= left[1])


def build_structure_routing_plan(
    path: Path, source_root: Path, selected_pages: set[int] | None = None
) -> StructureRoutingPlan:
    """Prefer structural vector candidates, then route remaining images to visual benchmark."""
    vector_evidence = extract_vector_evidence(path, source_root, selected_pages)
    structure = extract_vector_structure(path, source_root, selected_pages)
    routes = [
        ExtractionRoute(
            id=candidate.id,
            route="vector-geometry-benchmark",
            candidate=candidate.kind,
            source=candidate.source,
        )
        for candidate in structure.candidates
    ]
    structure_regions = [candidate.source for candidate in structure.candidates]
    for page in vector_evidence.pages:
        for region in page.regions:
            if region.kind != "embedded-image":
                continue
            if any(
                existing.page == region.source.page and _overlaps(existing.bbox, region.source.bbox)
                for existing in structure_regions
            ):
                continue
            routes.append(
                ExtractionRoute(
                    id=f"{region.id}-visual",
                    route="visual-model-benchmark",
                    candidate="paddleocr-vl-or-approved-fallback",
                    source=region.source,
                )
            )
    return StructureRoutingPlan(vector_evidence.source_checksum, routes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private PDF structure routing plan")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--pages", type=int, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_structure_routing_plan(args.input, args.source_root, set(args.pages or []))
    except PdfSafetyError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
