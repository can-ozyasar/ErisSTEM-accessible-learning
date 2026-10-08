"""Verified speech and Braille contracts for formula, table and chart content.

These functions never infer educational facts. Formula speech and chart summaries
are supplied by a verified upstream adapter; table narration is derived only
from already-verified cells.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .accessible_content import QualityEvidence


class FormulaAccessibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mathml: str = Field(min_length=13, max_length=5000)
    short_spoken_text: str = Field(min_length=1, max_length=2000)
    detailed_spoken_text: str = Field(min_length=1, max_length=5000)
    quality: QualityEvidence

    @model_validator(mode="after")
    def verified_mathml(self) -> FormulaAccessibility:
        if "<math" not in self.mathml or "</math>" not in self.mathml:
            raise ValueError("formula requires a MathML root")
        return self


class AccessibleTableCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row: int = Field(ge=1)
    column: int = Field(ge=1)
    role: Literal["header", "data"]
    text: str = Field(max_length=4000)


class TableAccessibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cells: list[AccessibleTableCell] = Field(min_length=1, max_length=500)
    quality: QualityEvidence

    @model_validator(mode="after")
    def rectangular_unique_grid(self) -> TableAccessibility:
        positions = {(cell.row, cell.column) for cell in self.cells}
        if len(positions) != len(self.cells):
            raise ValueError("table cells must be unique")
        return self


class ChartAccessibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_axis_label: str = Field(min_length=1, max_length=500)
    y_axis_label: str = Field(min_length=1, max_length=500)
    spoken_summary: str = Field(min_length=1, max_length=5000)
    quality: QualityEvidence


class BrailleAdapterRequest(BaseModel):
    """Portable input to a real Braille engine; not a pretend Unicode output."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["braille-adapter-request-v1"] = "braille-adapter-request-v1"
    content_kind: Literal["text", "formula", "table", "chart"]
    language: Literal["tr"] = "tr"
    braille_code: Literal["turkish-literary", "turkish-mathematics"]
    source_text: str | None = Field(default=None, max_length=8000)
    mathml: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def use_a_real_source_representation(self) -> BrailleAdapterRequest:
        if self.content_kind == "formula":
            if not self.mathml:
                raise ValueError("formula Braille requires verified MathML")
        elif not self.source_text:
            raise ValueError("non-formula Braille requires verified source text")
        return self


def require_release_quality(quality: QualityEvidence) -> None:
    if not (
        quality.source_bound
        and quality.schema_valid
        and quality.render_valid
        and quality.source_agreement == 1
        and quality.confidence == 1
        and quality.gold_gate_passed
        and quality.critical_error_count == 0
    ):
        raise ValueError("type-specific accessibility requires fully verified quality evidence")


def table_spoken_overview(table: TableAccessibility) -> str:
    """Describe navigation structure, never fabricate header/value relationships."""
    require_release_quality(table.quality)
    rows = max(cell.row for cell in table.cells)
    columns = max(cell.column for cell in table.cells)
    headers = sum(cell.role == "header" for cell in table.cells)
    return f"Tablo: {rows} satır, {columns} sütun, {headers} başlık hücresi."


def formula_braille_request(formula: FormulaAccessibility) -> BrailleAdapterRequest:
    require_release_quality(formula.quality)
    return BrailleAdapterRequest(content_kind="formula", braille_code="turkish-mathematics", mathml=formula.mathml)


def chart_braille_request(chart: ChartAccessibility) -> BrailleAdapterRequest:
    require_release_quality(chart.quality)
    return BrailleAdapterRequest(
        content_kind="chart", braille_code="turkish-literary", source_text=chart.spoken_summary
    )
