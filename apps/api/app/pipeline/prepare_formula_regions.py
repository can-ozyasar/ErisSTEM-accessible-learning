"""Build private, source-bound formula crops and a separate evaluation Gold file."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .formula_benchmark import FORMULA_GOLD_SCHEMA, INPUT_SCHEMA
from .pdf_text_layer import PdfSafetyError, _read_and_validate

ANNOTATION_SCHEMA = "formula-region-annotations-v1"
RENDER_SCALE = 4
MARGIN = 3


class FormulaAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    page: int = Field(ge=1, le=300)
    bbox: tuple[float, float, float, float]
    visible_notation: str = Field(min_length=1, max_length=1000)
    spoken_text: str = Field(min_length=1, max_length=3000)
    critical: bool = True

    @model_validator(mode="after")
    def positive_bbox(self) -> FormulaAnnotation:
        if self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]:
            raise ValueError("formula bbox must have positive area")
        return self


class FormulaAnnotations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    formulas: list[FormulaAnnotation] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_ids(self) -> FormulaAnnotations:
        ids = [formula.id for formula in self.formulas]
        if self.schema_version != ANNOTATION_SCHEMA or len(ids) != len(set(ids)):
            raise ValueError("invalid formula annotation manifest")
        return self


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_formula_regions(
    source_pdf: Path, source_root: Path, annotations_path: Path, output_dir: Path, gold_output: Path
) -> tuple[dict, dict]:
    """Render only teacher-marked complete expressions; never infer a bbox from text."""
    _, content = _read_and_validate(source_pdf, source_root)
    annotations = FormulaAnnotations.model_validate_json(annotations_path.read_text(encoding="utf-8"))
    checksum = hashlib.sha256(content).hexdigest()
    images = output_dir / "images"
    images.mkdir(parents=True, exist_ok=True)
    regions, gold = [], []
    with pymupdf.open(stream=content, filetype="pdf") as document:
        for item in annotations.formulas:
            if item.page > document.page_count:
                raise PdfSafetyError("formula annotation page outside PDF")
            page = document[item.page - 1]
            rectangle = pymupdf.Rect(item.bbox) + (-MARGIN, -MARGIN, MARGIN, MARGIN)
            rectangle = rectangle & page.rect
            if rectangle.is_empty:
                raise PdfSafetyError("formula annotation crop is outside page")
            path = images / f"{item.id}.png"
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(RENDER_SCALE, RENDER_SCALE), clip=rectangle, alpha=False)
            path.write_bytes(pixmap.tobytes("png"))
            regions.append({
                "id": item.id, "asset_path": str(path.relative_to(output_dir)), "asset_checksum": sha256(path),
                "source_checksum": checksum, "page": item.page, "bbox": item.bbox,
            })
            gold.append({"id": item.id, "visible_notation": item.visible_notation, "spoken_text": item.spoken_text, "critical": item.critical})
    input_manifest = {"schema_version": INPUT_SCHEMA, "regions": regions}
    gold_manifest = {"schema_version": FORMULA_GOLD_SCHEMA, "formulas": gold}
    (output_dir / "formula-region-manifest.json").write_text(json.dumps(input_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    gold_output.parent.mkdir(parents=True, exist_ok=True)
    gold_output.write_text(json.dumps(gold_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return input_manifest, gold_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare private formula-region benchmark")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("data/meb"))
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gold-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        inputs, gold = prepare_formula_regions(args.input, args.source_root, args.annotations, args.output_dir, args.gold_output)
    except (OSError, ValueError, PdfSafetyError) as error:
        parser.error(str(error))
    print(json.dumps({"formula_regions": len(inputs["regions"]), "gold_formulas": len(gold["formulas"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
