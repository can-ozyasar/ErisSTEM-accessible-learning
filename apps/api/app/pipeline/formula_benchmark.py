"""Strict, private evaluation contract for whole mathematical expressions.

Formula OCR is not treated as ordinary text OCR.  A candidate may only pass
when it found the source region, returned one complete expression and preserved
every mathematical-critical token.  The expected expressions remain in a
separate private Gold file; model runners never receive them.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, model_validator

INPUT_SCHEMA = "formula-region-benchmark-input-v1"
FORMULA_GOLD_SCHEMA = "formula-region-gold-v1"
FORMULA_PREDICTIONS_SCHEMA = "formula-region-predictions-v1"


class FormulaRegion(BaseModel):
    """A source-bound image crop that an OCR candidate is allowed to read."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    asset_path: str = Field(min_length=1, max_length=500)
    asset_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    page: int = Field(ge=1, le=300)
    bbox: tuple[float, float, float, float]

    @model_validator(mode="after")
    def valid_bbox(self) -> FormulaRegion:
        left, top, right, bottom = self.bbox
        if left >= right or top >= bottom:
            raise ValueError("formula region bbox must have positive area")
        return self


class FormulaBenchmarkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    regions: list[FormulaRegion] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_ids(self) -> FormulaBenchmarkInput:
        ids = [region.id for region in self.regions]
        if len(ids) != len(set(ids)):
            raise ValueError("formula region ids must be unique")
        return self


class FormulaGold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    visible_notation: str = Field(min_length=1, max_length=1000)
    spoken_text: str = Field(min_length=1, max_length=3000)
    critical: bool = True


class FormulaGoldManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    formulas: list[FormulaGold] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_ids(self) -> FormulaGoldManifest:
        ids = [formula.id for formula in self.formulas]
        if len(ids) != len(set(ids)):
            raise ValueError("formula Gold ids must be unique")
        return self


class FormulaPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    visible_notation: str = Field(default="", max_length=1000)
    confidence: float = Field(ge=0, le=1)
    status: str = Field(pattern=r"^(completed|no-formula|failed)$")


class FormulaPredictionsManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    candidate: str = Field(min_length=1, max_length=100)
    predictions: list[FormulaPrediction] = Field(max_length=200)

    @model_validator(mode="after")
    def unique_ids(self) -> FormulaPredictionsManifest:
        ids = [prediction.id for prediction in self.predictions]
        if len(ids) != len(set(ids)):
            raise ValueError("formula prediction ids must be unique")
        return self


_ALIASES = {
    r"\sqrt": "√",
    r"\cdot": "×",
    r"\times": "×",
    r"\div": "÷",
    r"\leq": "≤",
    r"\le": "≤",
    r"\geq": "≥",
    r"\ge": "≥",
    r"\neq": "≠",
    r"\in": "∈",
    r"\mathbb{r}": "ℝ",
}
_CRITICAL = re.compile(r"√|/|÷|×|·|\^|_|=|≤|≥|≠|<|>|∈|∉|[0-9]+|[A-Za-zα-ωΑ-Ωℝ]+")


def canonical_notation(value: str) -> str:
    """Canonicalise harmless display aliases; never repair mathematical structure."""
    result = unicodedata.normalize("NFKC", value).casefold()
    for source, target in _ALIASES.items():
        result = result.replace(source, target)
    result = result.replace("−", "-").replace("*", "×").replace("·", "×")
    return "".join(result.split()).replace("{", "(").replace("}", ")")


def critical_tokens(value: str) -> Counter[str]:
    """Return structure-sensitive tokens, including repeated roots and divisors."""
    return Counter(_CRITICAL.findall(canonical_notation(value)))


def evaluate_formula_predictions(
    inputs: FormulaBenchmarkInput,
    gold: FormulaGoldManifest,
    predictions: FormulaPredictionsManifest,
) -> dict:
    """Evaluate a candidate without ever emitting expected source expressions."""
    if inputs.schema_version != INPUT_SCHEMA or gold.schema_version != FORMULA_GOLD_SCHEMA:
        raise ValueError("invalid formula benchmark schema")
    if predictions.schema_version != FORMULA_PREDICTIONS_SCHEMA:
        raise ValueError("invalid formula prediction schema")
    input_ids = {region.id for region in inputs.regions}
    gold_by_id = {formula.id: formula for formula in gold.formulas}
    if input_ids != set(gold_by_id):
        raise ValueError("input and local formula Gold ids do not match")
    actual_by_id = {prediction.id: prediction for prediction in predictions.predictions}
    unexpected = sorted(set(actual_by_id) - input_ids)
    records, exact, critical_exact, completed = [], 0, 0, 0
    critical_total = sum(formula.critical for formula in gold.formulas)
    for formula_id in sorted(input_ids):
        expected, prediction = gold_by_id[formula_id], actual_by_id.get(formula_id)
        candidate = prediction.visible_notation if prediction else ""
        is_completed = prediction is not None and prediction.status == "completed"
        exact_match = is_completed and canonical_notation(candidate) == canonical_notation(expected.visible_notation)
        token_match = is_completed and critical_tokens(candidate) == critical_tokens(expected.visible_notation)
        completed += is_completed
        exact += exact_match
        critical_exact += expected.critical and exact_match and token_match
        records.append({
            "id": formula_id,
            "status": prediction.status if prediction else "missing",
            "exact_notation": exact_match,
            "critical_tokens_match": token_match,
            "confidence": prediction.confidence if prediction else None,
            "decision": "candidate-ready-for-teacher-review" if exact_match and token_match else "teacher-review-required",
        })
    total = len(input_ids)
    exact_accuracy = exact / total
    critical_accuracy = critical_exact / max(critical_total, 1)
    detection_recall = completed / total
    passes = (
        not unexpected
        and len(actual_by_id) == total
        and detection_recall >= 0.95
        and exact_accuracy >= 0.98
        and critical_accuracy == 1.0
    )
    return {
        "report_type": "formula-region-evaluation-v1",
        "contains_document_content": False,
        "candidate": predictions.candidate,
        "formula_regions": total,
        "completed_predictions": completed,
        "detection_recall": detection_recall,
        "exact_notation_accuracy": exact_accuracy,
        "critical_expression_accuracy": critical_accuracy,
        "unexpected_prediction_ids": unexpected,
        # A failed Gold gate must never stop an authorised teacher from seeing
        # the candidate beside its source crop.  It only prevents promotion to
        # a high-confidence/automatic suggestion lane.
        "decision": (
            "formula-gate-passed-teacher-review-still-required"
            if passes
            else "formula-gate-failed-experimental-review-allowed"
        ),
        "records": records,
    }
