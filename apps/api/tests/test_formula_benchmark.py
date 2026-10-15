from app.pipeline.formula_benchmark import (
    FORMULA_GOLD_SCHEMA,
    FORMULA_PREDICTIONS_SCHEMA,
    INPUT_SCHEMA,
    FormulaBenchmarkInput,
    FormulaGoldManifest,
    FormulaPredictionsManifest,
    evaluate_formula_predictions,
)


def manifests(prediction: str = r"\sqrt[5]{24} / \sqrt[5]{3}"):
    inputs = FormulaBenchmarkInput.model_validate({"schema_version": INPUT_SCHEMA, "regions": [
        {"id": "root-fraction", "asset_path": "images/root-fraction.png", "asset_checksum": "a" * 64,
         "source_checksum": "b" * 64, "page": 29, "bbox": [1, 2, 30, 40]}
    ]})
    gold = FormulaGoldManifest.model_validate({"schema_version": FORMULA_GOLD_SCHEMA, "formulas": [
        {"id": "root-fraction", "visible_notation": r"\sqrt[5]{24} / \sqrt[5]{3}", "spoken_text": "beş dereceden kök içinde yirmi dört bölü beş dereceden kök içinde üç"}
    ]})
    predictions = FormulaPredictionsManifest.model_validate({"schema_version": FORMULA_PREDICTIONS_SCHEMA, "candidate": "pp-formulanet-plus-l", "predictions": [
        {"id": "root-fraction", "visible_notation": prediction, "confidence": 0.99, "status": "completed"}
    ]})
    return inputs, gold, predictions


def test_formula_gate_accepts_equivalent_display_aliases_but_keeps_teacher_review():
    report = evaluate_formula_predictions(*manifests("√[5](24)/√[5](3)"))
    assert report["decision"] == "formula-gate-passed-teacher-review-still-required"
    assert report["exact_notation_accuracy"] == 1


def test_formula_gate_rejects_a_missing_root_degree_even_at_high_model_confidence():
    report = evaluate_formula_predictions(*manifests(r"\sqrt{24} / \sqrt[5]{3}"))
    assert report["decision"] == "formula-gate-failed-experimental-review-allowed"
    assert report["critical_expression_accuracy"] == 0
