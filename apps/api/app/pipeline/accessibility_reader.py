"""Build safe, type-aware reading plans for screen readers, TTS and Braille."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .accessible_content import CanonicalAccessibleBlock, release_decision


class ReadingUnit(BaseModel):
    """A content-free control contract around already-validated block content."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    navigation_label: str
    spoken_text: str
    braille_available: bool
    reading_order: int = Field(ge=1)


class ReadingPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "accessible-reading-plan-v1"
    units: list[ReadingUnit] = Field(min_length=1)


def build_reading_plan(blocks: list[CanonicalAccessibleBlock]) -> ReadingPlan:
    """Reject unsafe items instead of silently supplying a TTS fallback."""
    if not blocks:
        raise ValueError("reading plan requires at least one block")
    ids = [block.id for block in blocks]
    orders = [block.reading_order for block in blocks]
    if len(ids) != len(set(ids)) or len(orders) != len(set(orders)):
        raise ValueError("reading plan block ids and reading order must be unique")
    units = []
    for block in sorted(blocks, key=lambda value: value.reading_order):
        decision, reasons = release_decision(block)
        if decision != "auto-approved":
            raise ValueError(f"block {block.id} is not safe for student reading: {', '.join(reasons)}")
        spoken = block.representations.spoken_text
        if not spoken:
            raise ValueError(f"block {block.id} has no verified spoken representation")
        units.append(
            ReadingUnit(
                id=block.id,
                kind=block.kind,
                navigation_label=block.representations.navigation_label,
                spoken_text=spoken,
                braille_available=block.representations.braille_source is not None,
                reading_order=block.reading_order,
            )
        )
    return ReadingPlan(units=units)
