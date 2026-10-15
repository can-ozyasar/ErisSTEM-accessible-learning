import pytest

from app.pipeline.math_notation import MathNotationError, notation_speech_candidate


@pytest.mark.parametrize(("notation", "spoken"), [
    ("5/3", "beş bölü üç"),
    (r"\sqrt{6}", "karekök içinde altı"),
    (r"\sqrt[3]{7}", "üç dereceden kök içinde yedi"),
    (r"\sqrt[5]{16}", "beş dereceden kök içinde on altı"),
    (r"\sqrt[7]{5^3}", "yedi dereceden kök içinde beş küpü"),
    ("2·3 + 2·1 = 8 cm", "iki çarpı üç artı iki çarpı bir eşittir sekiz santimetre"),
    ("165 < x < 178, x ∈ ℝ", "yüz altmış beş küçüktür x küçüktür yüz yetmiş sekiz"),
])
def test_teacher_visible_notation_becomes_one_verified_mathml_expression(notation, spoken):
    mathml, candidate = notation_speech_candidate(notation)
    assert mathml.startswith("<math>")
    assert candidate.startswith(spoken)


def test_measurement_requires_explicit_teacher_verified_shape_context():
    _, candidate = notation_speech_candidate("8 cm", measurement_label="AB kenarı")
    assert candidate == "AB kenarı ölçüsü: sekiz santimetre"


@pytest.mark.parametrize("notation", ["5 /", "√6", "x @ 2", r"\sqrt[3]{"])
def test_unbounded_or_incomplete_notation_fails_closed(notation):
    with pytest.raises(MathNotationError):
        notation_speech_candidate(notation)
