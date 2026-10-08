import pytest

from app.pipeline.turkish_math_speech import MathSpeechError, turkish_math_speech_plan
from app.pipeline.type_specific_accessibility import FormulaAccessibility


def formula(mathml: str, **quality_overrides):
    return FormulaAccessibility.model_validate({
        "mathml": mathml,
        "short_spoken_text": "upstream verified short reading",
        "detailed_spoken_text": "upstream verified detailed reading",
        "quality": {
            "source_bound": True, "schema_valid": True, "render_valid": True,
            "source_agreement": 1, "confidence": 1, "gold_gate_passed": True,
            "critical_error_count": 0, **quality_overrides,
        },
    })


def test_compiles_verified_addition_and_equality_without_an_ai_guess():
    plan = turkish_math_speech_plan(formula(
        "<math><mrow><mn>2</mn><mi>x</mi><mo>+</mo><mn>3</mn><mo>=</mo><mn>11</mn></mrow></math>"
    ))

    assert plan.spoken_text == "iki x artı üç eşittir on bir"
    assert plan.ruleset_version == "turkish-math-speech-v1"
    assert len(plan.source_mathml_sha256) == 64


def test_compiles_fraction_power_root_and_set_operators():
    fraction = turkish_math_speech_plan(formula(
        "<math><mfrac><mn>1</mn><mn>2</mn></mfrac></math>"
    ))
    power = turkish_math_speech_plan(formula(
        "<math><msup><mi>x</mi><mn>2</mn></msup></math>"
    ))
    root = turkish_math_speech_plan(formula("<math><msqrt><mn>16</mn></msqrt></math>"))
    sets = turkish_math_speech_plan(formula(
        "<math><mrow><mi>A</mi><mo>∩</mo><mi>B</mi><mo>=</mo><mo>∅</mo></mrow></math>"
    ))

    assert fraction.spoken_text == "bir bölü iki"
    assert power.spoken_text == "x karesi"
    assert root.spoken_text == "karekök içinde on altı"
    assert sets.spoken_text == "A kesişim B eşittir boş küme"


@pytest.mark.parametrize("mathml", [
    "<math><mstyle><mi>x</mi></mstyle></math>",
    "<math><mi>x</mi><script>alert(1)</script></math>",
    "<!DOCTYPE math [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><math><mi>&xxe;</mi></math>",
    "<math><mfrac><mi>x</mi></mfrac></math>",
])
def test_rejects_unsupported_or_unsafe_mathml(mathml):
    with pytest.raises(MathSpeechError):
        turkish_math_speech_plan(formula(mathml))


def test_refuses_to_build_a_student_reading_before_formula_quality_gate():
    with pytest.raises(ValueError, match="fully verified"):
        turkish_math_speech_plan(formula("<math><mi>x</mi></math>", confidence=0.7))
