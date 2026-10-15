import pytest

from app.pipeline.latex_ocr_adapter import (
    LatexOcrError,
    latex_ocr_candidate,
    latex_to_visible_notation,
)


def test_formula_ocr_latex_becomes_normal_notation_mathml_and_turkish_speech():
    visible, mathml, spoken = latex_ocr_candidate(r"2^{\frac{3}{2}} = \sqrt{2^3} = \sqrt{8}")
    assert visible == "2^(3/2) = √(2^3) = √(8)"
    assert mathml.startswith("<math>")
    assert "karekök içinde sekiz" in spoken


def test_unknown_latex_command_is_not_guessed():
    with pytest.raises(LatexOcrError, match="unsupported_latex_command"):
        latex_to_visible_notation(r"\overline{x}")


def test_negative_base_is_not_misread_as_a_less_than_command():
    visible, _, spoken = latex_ocr_candidate(r"\left(-2\right)^{\frac{3}{5}}=\sqrt[5]{-8}")
    assert visible == "(-2)^(3/5)=√[5](-8)"
    assert "beş dereceden kök içinde eksi sekiz" in spoken
