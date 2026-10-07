"""Strict teacher-review models for vector/native PDF table candidates.

The teacher receives ordinary cell text and a source rectangle only. OCR markup,
LaTex, model HTML, confidence scores, and raw extractor artefacts never enter
this API representation.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .pipeline.visual_result_schema import SourceRegion, TableCellDraft

_LATEX_COMMAND = re.compile(r"\\(?:frac|sqrt|begin|end|left|right|text|mathrm)\b", re.IGNORECASE)


class VectorNativeTableIngress(BaseModel):
    """Private worker-to-review API envelope; never a browser upload payload."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,200}$")
    document_id: str = Field(min_length=1, max_length=100)
    schema_version: Literal["visual-table-draft-v1"]
    kind: Literal["table"]
    source: SourceRegion
    cells: list[TableCellDraft] = Field(min_length=1, max_length=500)
    confidence: Literal[0.0]
    publication_status: Literal["requires-gold-and-teacher-review"]
    candidate_status: Literal["candidate-vector-native-needs-gold-and-review"]

    @model_validator(mode="after")
    def unique_cells_and_safe_text(self) -> VectorNativeTableIngress:
        coordinates = [(cell.row, cell.column) for cell in self.cells]
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("table cells must have unique row/column coordinates")
        if any(_LATEX_COMMAND.search(cell.text) for cell in self.cells):
            raise ValueError("LaTeX komutları öğretmen tablo taslağına alınamaz")
        return self


class TeacherTableCell(BaseModel):
    """The only editable table value exposed to the teacher browser."""

    model_config = ConfigDict(extra="forbid")

    row: int = Field(ge=1)
    column: int = Field(ge=1)
    role: Literal["header", "data", "unknown"]
    text: str = Field(max_length=4000)

    @field_validator("text")
    @classmethod
    def no_latex_markup(cls, value: str) -> str:
        if _LATEX_COMMAND.search(value):
            raise ValueError("LaTeX komutları kabul edilmez")
        return value


class TeacherTableSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float]

    @model_validator(mode="after")
    def valid_bbox(self) -> TeacherTableSource:
        if self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]:
            raise ValueError("bbox must have positive area")
        return self


class TeacherTableReview(BaseModel):
    """Teacher-safe projection of a pending or approved table review."""

    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    source: TeacherTableSource
    cells: list[TeacherTableCell]
    status: Literal["review_required", "approved", "published"]
    revision: int = Field(ge=1)


class TableReviewCorrection(BaseModel):
    cells: list[TeacherTableCell] = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=5, max_length=500)
    expected_revision: int = Field(ge=1)

    @model_validator(mode="after")
    def same_cell_coordinate_rule(self) -> TableReviewCorrection:
        coordinates = [(cell.row, cell.column) for cell in self.cells]
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("Hücre koordinatları benzersiz olmalı")
        return self


class TableReviewApproval(BaseModel):
    reason: str = Field(min_length=5, max_length=500)
    expected_revision: int = Field(ge=1)


class PublishedTable(BaseModel):
    """Student projection: no source coordinates or extraction metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str
    cells: list[TeacherTableCell]


def teacher_projection(payload: dict, status: str, revision: int) -> TeacherTableReview:
    """Strip extraction-only fields before serialising to the teacher browser."""
    return TeacherTableReview.model_validate(
        {
            "id": payload["id"],
            "document_id": payload["document_id"],
            "source": {"page": payload["source"]["page"], "bbox": payload["source"]["bbox"]},
            "cells": [
                {key: cell[key] for key in ("row", "column", "role", "text")}
                for cell in payload["cells"]
            ],
            "status": status,
            "revision": revision,
        }
    )
