"""Strict, non-HTML schemas for visual table/chart extraction candidates."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region_id: str = Field(min_length=1, max_length=200)
    source_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float]

    @model_validator(mode="after")
    def valid_bbox(self) -> SourceRegion:
        if self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]:
            raise ValueError("bbox must have positive width and height")
        return self


class TableCellDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row: int = Field(ge=1)
    column: int = Field(ge=1)
    role: Literal["header", "data", "unknown"]
    text: str = Field(max_length=4000)
    confidence: float = Field(ge=0, le=1)


class VisualTableDraft(BaseModel):
    """A candidate only; calling code must still validate and route for review."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["table"]
    source: SourceRegion
    cells: list[TableCellDraft] = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def unique_cells(self) -> VisualTableDraft:
        coordinates = [(cell.row, cell.column) for cell in self.cells]
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("table cells must have unique row/column coordinates")
        return self


class ChartAxisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, max_length=500)
    tick_labels: list[str] = Field(default_factory=list, max_length=100)


class ChartSeriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_label: str | None = Field(default=None, max_length=500)
    y_value: float | None = None
    confidence: float = Field(ge=0, le=1)


class VisualChartDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["chart"]
    source: SourceRegion
    x_axis: ChartAxisDraft
    y_axis: ChartAxisDraft
    series: list[ChartSeriesPoint] = Field(default_factory=list, max_length=500)
    confidence: float = Field(ge=0, le=1)
