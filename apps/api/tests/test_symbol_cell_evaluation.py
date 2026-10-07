import pytest

from app.pipeline.symbol_cell_evaluation import (
    SymbolGoldManifest,
    SymbolInputManifest,
    SymbolPredictionsManifest,
    canonical_symbol,
    evaluate_symbol_predictions,
)


def inputs() -> SymbolInputManifest:
    return SymbolInputManifest.model_validate(
        {"schema_version": "symbol-cell-benchmark-input-v1", "assets": [{"id": "cell-1"}, {"id": "cell-2"}]}
    )


def gold() -> SymbolGoldManifest:
    return SymbolGoldManifest.model_validate(
        {"schema_version": "symbol-cell-gold-v1", "expected": [{"id": "cell-1", "expected": "∈"}, {"id": "cell-2", "expected": "∩"}]}
    )


def test_symbol_evaluation_allows_only_known_notation_equivalence():
    predictions = SymbolPredictionsManifest.model_validate(
        {"schema_version": "symbol-cell-predictions-v1", "candidate": "candidate-a", "predictions": [{"id": "cell-1", "prediction": r"\in", "status": "completed"}, {"id": "cell-2", "prediction": "∩", "status": "completed"}]}
    )

    report = evaluate_symbol_predictions(inputs(), gold(), predictions)

    assert canonical_symbol(r"\in") == "∈"
    assert report["exact_symbol_accuracy"] == 1.0
    assert report["decision"] == "symbol-benchmark-passed-teacher-review-still-required"
    assert report["contains_document_content"] is False


def test_symbol_evaluation_blocks_missing_or_wrong_glyphs_without_exposing_gold():
    predictions = SymbolPredictionsManifest.model_validate(
        {"schema_version": "symbol-cell-predictions-v1", "candidate": "candidate-a", "predictions": [{"id": "cell-1", "prediction": "!", "status": "completed"}]}
    )

    report = evaluate_symbol_predictions(inputs(), gold(), predictions)

    assert report["exact_symbol_accuracy"] == 0.0
    assert report["decision"] == "symbol-benchmark-blocked"
    assert all("expected" not in record for record in report["records"])


def test_symbol_evaluation_rejects_mismatched_gold_ids():
    mismatched = SymbolGoldManifest.model_validate(
        {"schema_version": "symbol-cell-gold-v1", "expected": [{"id": "other", "expected": "∈"}]}
    )
    predictions = SymbolPredictionsManifest.model_validate(
        {"schema_version": "symbol-cell-predictions-v1", "candidate": "candidate-a", "predictions": []}
    )

    with pytest.raises(ValueError, match="ids do not match"):
        evaluate_symbol_predictions(inputs(), mismatched, predictions)
