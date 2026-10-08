"""Canonical, source-bound accessibility content and conservative release gates.

This is deliberately model-agnostic: OCR/VLM candidates may propose content,
but only type-specific evidence can move a block beyond review.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ContentKind = Literal["heading", "paragraph", "formula", "table", "chart", "exercise"]
ReleaseDecision = Literal["auto-approved", "review-required", "blocked"]


class AccessibilityRepresentations(BaseModel):
    """Outputs consumed by screen readers, TTS and future Braille adapters."""

    model_config = ConfigDict(extra="forbid")

    spoken_text: str | None = Field(default=None, max_length=8000)
    mathml: str | None = Field(default=None, max_length=5000)
    braille_source: str | None = Field(default=None, max_length=8000)
    navigation_label: str = Field(min_length=1, max_length=300)


class QualityEvidence(BaseModel):
    """Machine-checkable evidence; confidence alone is never sufficient."""

    model_config = ConfigDict(extra="forbid")

    source_bound: bool
    schema_valid: bool
    render_valid: bool
    source_agreement: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    gold_gate_passed: bool = False
    critical_error_count: int = Field(ge=0)


class CanonicalAccessibleBlock(BaseModel):
    """One publishable-unit candidate; content remains source-coordinate bound."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    kind: ContentKind
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float]
    reading_order: int = Field(ge=1)
    representations: AccessibilityRepresentations
    quality: QualityEvidence

    @model_validator(mode="after")
    def accessibility_is_type_complete(self) -> CanonicalAccessibleBlock:
        x0, y0, x1, y1 = self.bbox
        if x0 >= x1 or y0 >= y1:
            raise ValueError("bbox must have positive area")
        if self.kind == "formula" and not (self.representations.mathml and self.representations.spoken_text):
            raise ValueError("formula requires MathML and a spoken representation")
        if self.kind in {"table", "chart", "exercise"} and not self.representations.spoken_text:
            raise ValueError(f"{self.kind} requires a spoken representation")
        return self


def release_decision(block: CanonicalAccessibleBlock) -> tuple[ReleaseDecision, list[str]]:
    """Return an explainable, type-aware decision without trusting an AI score alone."""
    evidence = block.quality
    reasons: list[str] = []
    if not evidence.source_bound:
        reasons.append("source-not-bound")
    if not evidence.schema_valid:
        reasons.append("schema-invalid")
    if not evidence.render_valid:
        reasons.append("render-invalid")
    if evidence.critical_error_count:
        reasons.append("critical-errors")
    if reasons:
        return "blocked", reasons
    if evidence.source_agreement < 0.995:
        reasons.append("source-agreement-below-auto-threshold")
    if evidence.confidence < 0.995:
        reasons.append("confidence-below-auto-threshold")
    if block.kind in {"formula", "table", "chart", "exercise"} and not evidence.gold_gate_passed:
        reasons.append("type-specific-gold-gate-not-passed")
    if reasons:
        return "review-required", reasons
    return "auto-approved", ["all-automatic-quality-gates-passed"]
