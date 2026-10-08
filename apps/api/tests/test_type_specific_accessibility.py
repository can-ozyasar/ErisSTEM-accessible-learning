import pytest

from app.pipeline.type_specific_accessibility import (
    BrailleAdapterRequest,
    ChartAccessibility,
    FormulaAccessibility,
    TableAccessibility,
    chart_braille_request,
    formula_braille_request,
    table_spoken_overview,
)


def quality(**overrides):
    return {
        "source_bound": True, "schema_valid": True, "render_valid": True,
        "source_agreement": 1, "confidence": 1, "gold_gate_passed": True,
        "critical_error_count": 0, **overrides,
    }


def test_formula_keeps_short_and_detailed_verified_readings_and_emits_math_braille_contract():
    formula = FormulaAccessibility.model_validate({
        "mathml": "<math><mi>x</mi></math>", "short_spoken_text": "x", "detailed_spoken_text": "x değişkeni", "quality": quality(),
    })

    request = formula_braille_request(formula)

    assert request.braille_code == "turkish-mathematics"
    assert request.mathml == formula.mathml


def test_table_narration_is_structural_and_requires_verified_cells():
    table = TableAccessibility.model_validate({
        "cells": [{"row": 1, "column": 1, "role": "header", "text": "Başlık"}, {"row": 2, "column": 1, "role": "data", "text": "Değer"}],
        "quality": quality(),
    })

    assert table_spoken_overview(table) == "Tablo: 2 satır, 1 sütun, 1 başlık hücresi."


def test_chart_requires_a_verified_human_or_gold_checked_summary_before_braille():
    chart = ChartAccessibility.model_validate({
        "x_axis_label": "Yıl", "y_axis_label": "Değer", "spoken_summary": "Değer zamanla artar.", "quality": quality(),
    })

    assert chart_braille_request(chart).source_text == "Değer zamanla artar."
    unverified = ChartAccessibility.model_validate({
        "x_axis_label": "Yıl", "y_axis_label": "Değer", "spoken_summary": "Değer zamanla artar.",
        "quality": quality(confidence=0.8),
    })
    with pytest.raises(ValueError, match="verified"):
        chart_braille_request(unverified)


def test_braille_contract_refuses_fake_formula_text_without_mathml():
    with pytest.raises(ValueError, match="MathML"):
        BrailleAdapterRequest(content_kind="formula", braille_code="turkish-mathematics")
