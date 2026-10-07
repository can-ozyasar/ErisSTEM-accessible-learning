"""Private, strict evaluation for one-symbol mathematical OCR predictions."""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

INPUT_SCHEMA = "symbol-cell-benchmark-input-v1"
GOLD_SCHEMA = "symbol-cell-gold-v1"
PREDICTIONS_SCHEMA = "symbol-cell-predictions-v1"


class SymbolInputAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")


class SymbolInputManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    assets: list[SymbolInputAsset] = Field(min_length=1)


class SymbolGoldEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    expected: str = Field(min_length=1, max_length=128)


class SymbolGoldManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    expected: list[SymbolGoldEntry] = Field(min_length=1)


class SymbolPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    prediction: str = Field(max_length=128)
    status: str = Field(pattern=r"^(completed|no-text|failed)$")


class SymbolPredictionsManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    candidate: str = Field(min_length=1, max_length=80)
    predictions: list[SymbolPrediction]

    @model_validator(mode="after")
    def unique_ids(self) -> SymbolPredictionsManifest:
        ids = [item.id for item in self.predictions]
        if len(ids) != len(set(ids)):
            raise ValueError("prediction ids must be unique")
        return self


def canonical_symbol(value: str) -> str:
    """Allow notation equivalents only; never turn a wrong glyph into a match."""
    normalized = "".join(unicodedata.normalize("NFKC", value).split()).casefold()
    aliases = {
        r"\in": "∈",
        r"\notin": "∉",
        r"\subset": "⊂",
        r"\subseteq": "⊆",
        r"\cup": "∪",
        r"\cap": "∩",
        r"\emptyset": "∅",
        r"\varnothing": "∅",
        r"\setminus": "\\",
    }
    return aliases.get(normalized, normalized)


def evaluate_symbol_predictions(
    inputs: SymbolInputManifest, gold: SymbolGoldManifest, predictions: SymbolPredictionsManifest
) -> dict:
    if inputs.schema_version != INPUT_SCHEMA or gold.schema_version != GOLD_SCHEMA:
        raise ValueError("invalid symbol benchmark schema")
    if predictions.schema_version != PREDICTIONS_SCHEMA:
        raise ValueError("invalid symbol prediction schema")
    input_ids = {asset.id for asset in inputs.assets}
    gold_by_id = {entry.id: entry for entry in gold.expected}
    if input_ids != set(gold_by_id):
        raise ValueError("input and local Gold ids do not match")
    actual_by_id = {entry.id: entry for entry in predictions.predictions}
    unexpected = sorted(set(actual_by_id) - input_ids)
    records = []
    exact = completed = 0
    for asset_id in sorted(input_ids):
        prediction = actual_by_id.get(asset_id)
        if prediction is None:
            decision = "missing-prediction"
            status = "missing"
            matches = False
        else:
            status = prediction.status
            matches = status == "completed" and canonical_symbol(prediction.prediction) == canonical_symbol(gold_by_id[asset_id].expected)
            decision = "exact-symbol-match" if matches else "symbol-review-required"
            completed += status == "completed"
        exact += matches
        records.append({"id": asset_id, "status": status, "exact": matches, "decision": decision})
    complete = not unexpected and len(actual_by_id) == len(input_ids)
    accuracy = exact / len(input_ids)
    return {
        "report_type": "symbol-cell-evaluation-v1",
        "contains_document_content": False,
        "candidate": predictions.candidate,
        "symbol_cells": len(input_ids),
        "completed_predictions": completed,
        "unexpected_prediction_ids": unexpected,
        "exact_symbol_accuracy": accuracy,
        "decision": (
            "symbol-benchmark-passed-teacher-review-still-required"
            if complete and accuracy == 1.0
            else "symbol-benchmark-blocked"
        ),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate private mathematical symbol-cell predictions")
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = SymbolInputManifest.model_validate_json(args.input_manifest.read_text(encoding="utf-8"))
    gold = SymbolGoldManifest.model_validate_json(args.gold.read_text(encoding="utf-8"))
    predictions = SymbolPredictionsManifest.model_validate_json(args.predictions.read_text(encoding="utf-8"))
    report = evaluate_symbol_predictions(inputs, gold, predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("candidate", "symbol_cells", "exact_symbol_accuracy", "decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
