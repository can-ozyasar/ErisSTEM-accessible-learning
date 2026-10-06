"""Private, source-bound accuracy evaluation for visual table candidates.

Gold table content is derived from licensed MEB material and therefore remains
outside the repository. This module contains only the schema, metrics and CLI;
it never renders model markup or writes student-facing material.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .benchmark import character_error_rate, normalized
from .visual_result_schema import SourceRegion, VisualTableDraft

GOLD_SCHEMA_VERSION = "visual-table-gold-v1"
DRAFT_SCHEMA_VERSION = "visual-table-draft-v1"
MINIMUM_TABLE_GOLD_SAMPLES = 3


class GoldTableCell(BaseModel):
    """Human-verified private reference cell; intentionally has no model confidence."""

    model_config = ConfigDict(extra="forbid")

    row: int = Field(ge=1)
    column: int = Field(ge=1)
    role: Literal["header", "data", "unknown"]
    text: str = Field(min_length=1, max_length=4000)


class VisualTableGold(BaseModel):
    """One private reference table, cryptographically bound to its source region."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["visual-table-gold-v1"]
    kind: Literal["table"]
    source: SourceRegion
    cells: list[GoldTableCell] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_cells(self) -> VisualTableGold:
        coordinates = [(cell.row, cell.column) for cell in self.cells]
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("gold table cells must have unique row/column coordinates")
        return self


class VisualTableGoldManifest(BaseModel):
    """Private benchmark input. Its content must never be committed or published."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["visual-table-gold-v1"]
    tables: list[VisualTableGold] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_regions(self) -> VisualTableGoldManifest:
        region_ids = [table.source.region_id for table in self.tables]
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("gold manifest region ids must be unique")
        return self


@dataclass(frozen=True)
class TableEvaluation:
    region_id: str
    source_matches: bool
    structure_precision: float
    structure_recall: float
    structure_f1: float
    role_accuracy: float
    text_accuracy: float
    exact_cell_accuracy: float
    decision: str


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def _candidate_from_payload(payload: dict) -> VisualTableDraft:
    """Accept the Kaggle draft envelope, while rejecting arbitrary extra model fields."""
    draft_fields = {"kind", "source", "cells", "confidence"}
    envelope_fields = {"schema_version", "publication_status"}
    unknown = set(payload) - draft_fields - envelope_fields
    if unknown or payload.get("schema_version") != DRAFT_SCHEMA_VERSION:
        raise ValueError("invalid visual-table draft envelope")
    return VisualTableDraft.model_validate({key: value for key, value in payload.items() if key in draft_fields})


def _payload_region_id(payload: dict) -> str:
    source = payload.get("source")
    return str(source.get("region_id", "unknown")) if isinstance(source, dict) else "unknown"


def evaluate_table(candidate: VisualTableDraft, gold: VisualTableGold) -> TableEvaluation:
    """Score one candidate. A source mismatch is never allowed to become a pass."""
    source_matches = candidate.source.model_dump() == gold.source.model_dump()
    expected = {(cell.row, cell.column): cell for cell in gold.cells}
    actual = {(cell.row, cell.column): cell for cell in candidate.cells}
    shared = set(expected) & set(actual)
    precision = len(shared) / len(actual) if actual else 0.0
    recall = len(shared) / len(expected)
    structure_f1 = _f1(precision, recall)
    role_accuracy = (
        sum(expected[key].role == actual[key].role for key in shared) / len(expected) if expected else 0.0
    )
    text_accuracy = (
        sum(
            1 - character_error_rate(expected[key].text, actual[key].text)
            for key in expected
            if key in actual
        )
        / len(expected)
    )
    exact_cell_accuracy = (
        sum(
            expected[key].role == actual[key].role
            and normalized(expected[key].text) == normalized(actual[key].text)
            for key in expected
            if key in actual
        )
        / len(expected)
    )
    passed = source_matches and all(
        score == 1.0 for score in (structure_f1, role_accuracy, text_accuracy, exact_cell_accuracy)
    )
    return TableEvaluation(
        region_id=gold.source.region_id,
        source_matches=source_matches,
        structure_precision=precision,
        structure_recall=recall,
        structure_f1=structure_f1,
        role_accuracy=role_accuracy,
        text_accuracy=text_accuracy,
        exact_cell_accuracy=exact_cell_accuracy,
        decision="matches-gold" if passed else "requires-review-or-model-improvement",
    )


def evaluate_manifest(drafts: list[dict], gold: VisualTableGoldManifest) -> dict:
    """Create a content-free, conservative candidate-selection report."""
    drafts_by_region: dict[str, VisualTableDraft] = {}
    invalid_drafts: list[str] = []
    for payload in drafts:
        if not isinstance(payload, dict):
            invalid_drafts.append("unknown")
            continue
        try:
            candidate = _candidate_from_payload(payload)
        except (ValidationError, ValueError):
            invalid_drafts.append(_payload_region_id(payload))
            continue
        if candidate.source.region_id in drafts_by_region:
            invalid_drafts.append(candidate.source.region_id)
        else:
            drafts_by_region[candidate.source.region_id] = candidate

    evaluations = [
        evaluate_table(drafts_by_region[table.source.region_id], table)
        if table.source.region_id in drafts_by_region
        else TableEvaluation(
            region_id=table.source.region_id,
            source_matches=False,
            structure_precision=0.0,
            structure_recall=0.0,
            structure_f1=0.0,
            role_accuracy=0.0,
            text_accuracy=0.0,
            exact_cell_accuracy=0.0,
            decision="missing-candidate",
        )
        for table in gold.tables
    ]
    complete = len(evaluations) >= MINIMUM_TABLE_GOLD_SAMPLES
    all_match = not invalid_drafts and all(item.decision == "matches-gold" for item in evaluations)
    if not complete:
        candidate_decision = "blocked_insufficient_gold_samples"
    elif all_match:
        candidate_decision = "benchmark-passed-teacher-review-still-required"
    else:
        candidate_decision = "blocked_gold_gate_not_met"
    return {
        "report_type": "visual-table-gold-evaluation-v1",
        "contains_document_content": False,
        "minimum_gold_samples": MINIMUM_TABLE_GOLD_SAMPLES,
        "gold_samples": len(evaluations),
        "invalid_or_duplicate_draft_regions": sorted(invalid_drafts),
        "candidate_decision": candidate_decision,
        "evaluations": [asdict(item) for item in evaluations],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Private visual table Gold evaluation")
    parser.add_argument("--drafts", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    drafts = json.loads(args.drafts.read_text(encoding="utf-8"))
    if not isinstance(drafts, list):
        raise TypeError("draft input must be a JSON list")
    gold = VisualTableGoldManifest.model_validate_json(args.gold.read_text(encoding="utf-8"))
    args.output.write_text(json.dumps(evaluate_manifest(drafts, gold), ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
