"""Bounded adapter from formula-OCR LaTeX to reviewed visible notation.

Formula OCR commonly emits LaTeX, while the accessibility pipeline consumes
safe MathML and Turkish speech.  This adapter supports the printed-school-math
subset only and rejects unknown commands rather than inventing a reading.
"""

from __future__ import annotations

import re

from .math_notation import MathNotationError, notation_speech_candidate


class LatexOcrError(ValueError):
    """The OCR output is outside the supported, reviewable LaTeX subset."""


_COMMANDS = {
    r"\cdot": "×", r"\times": "×", r"\div": "÷", r"\leq": "≤", r"\le": "≤",
    r"\geq": "≥", r"\ge": "≥", r"\neq": "≠", r"\ne": "≠", r"\in": "∈",
    r"\notin": "∉", r"\mathbb{R}": "ℝ", r"\mathbb{r}": "ℝ", r"\,": "", r"\!": "",
    r"\left": "", r"\right": "",
}
_UNKNOWN_COMMAND = re.compile(r"\\[A-Za-z]+")


def _balanced_group(value: str, start: int) -> tuple[str, int]:
    if start >= len(value) or value[start] != "{":
        raise LatexOcrError("missing_latex_group")
    depth = 0
    for index in range(start, len(value)):
        if value[index] == "{":
            depth += 1
        elif value[index] == "}":
            depth -= 1
            if depth == 0:
                return value[start + 1:index], index + 1
    raise LatexOcrError("unclosed_latex_group")


def latex_to_visible_notation(latex: str) -> str:
    """Convert fractions and display aliases without evaluating mathematical content."""
    source = " ".join(latex.split())
    if not source or len(source) > 1000:
        raise LatexOcrError("invalid_latex_length")

    def convert(value: str) -> str:
        output, index = [], 0
        while index < len(value):
            if value.startswith(r"\frac", index):
                numerator, next_index = _balanced_group(value, index + len(r"\frac"))
                denominator, index = _balanced_group(value, next_index)
                numerator_visible, denominator_visible = convert(numerator), convert(denominator)
                # Keep elementary fractions compact so speech is "üç bölü iki",
                # rather than a sequence of syntax parentheses.
                wrap = lambda item: f"({item})" if re.search(r"[+=]", item) else item
                output.append(f"{wrap(numerator_visible)}/{wrap(denominator_visible)}")
                continue
            if value.startswith(r"\sqrt", index):
                index += len(r"\sqrt")
                degree = ""
                if index < len(value) and value[index] == "[":
                    end = value.find("]", index + 1)
                    if end < 0:
                        raise LatexOcrError("unclosed_root_degree")
                    degree, index = value[index:end + 1], end + 1
                radicand, index = _balanced_group(value, index)
                # Teacher UI receives printed notation, never the OCR model's
                # LaTeX control words.  The bounded parser accepts this same
                # Unicode root form.
                output.append("√" + degree + "(" + convert(radicand) + ")")
                continue
            if value[index] in "^_" and index + 1 < len(value) and value[index + 1] == "{":
                operator = value[index]
                group, index = _balanced_group(value, index + 1)
                # Grouping is explicit so the downstream grammar preserves the
                # exponent/subscript as one unit, not as adjacent characters.
                output.append(f"{operator}({convert(group)})")
                continue
            output.append(value[index])
            index += 1
        return "".join(output)

    # Longest first: ``\\left`` must win before the shorter ``\\le`` alias.
    for command, replacement in sorted(_COMMANDS.items(), key=lambda item: len(item[0]), reverse=True):
        source = source.replace(command, replacement)
    # These two commands are consumed recursively by ``convert`` below; all
    # other commands must have been normalised above.
    unsupported = re.sub(r"\\(?:frac|sqrt)", "", source)
    if _UNKNOWN_COMMAND.search(unsupported):
        raise LatexOcrError("unsupported_latex_command")
    # ``convert`` consumes all grouping braces except the braces required by
    # the downstream ``\sqrt{...}`` grammar.
    return " ".join(convert(source).split())


def latex_ocr_candidate(latex: str) -> tuple[str, str, str]:
    """Return normal visible notation, checked MathML and Turkish speech."""
    visible = latex_to_visible_notation(latex)
    try:
        mathml, spoken = notation_speech_candidate(visible)
    except MathNotationError as error:
        raise LatexOcrError(str(error)) from error
    return visible, mathml, spoken
