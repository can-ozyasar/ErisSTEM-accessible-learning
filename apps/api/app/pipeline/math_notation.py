"""Bounded source-notation compiler for teacher-reviewed maths.

PDF/OCR/VLM extraction is allowed to propose *one complete visual expression*.
This module never tries to repair a fragmented expression or infer geometry from
nearby pixels.  It compiles the teacher-visible notation to MathML and a
deterministic Turkish speech candidate; unsupported notation remains in review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .turkish_math_speech import MathSpeechError, compile_mathml_candidate


class MathNotationError(ValueError):
    """Visible notation is outside the small, reviewable grammar."""


_TOKEN = re.compile(
    r"\\sqrt|√|\\mathbb\{|\d+(?:[.,]\d+)?|[A-Za-zα-ωΑ-Ωℝ]+|<=|>=|!=|≤|≥|≠|∈|∉|"
    r"[+\-−*/÷×·=<>^_(){}\[\],|]"
)
_UNITS = {"cm": "santimetre", "mm": "milimetre", "m": "metre", "km": "kilometre", "°": "derece"}
_OPERATOR = {"*": "×", "·": "×", "÷": "/", "-": "−", "<=": "≤", ">=": "≥", "!=": "≠"}


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _mo(value: str) -> str:
    return f"<mo>{_escape(value)}</mo>"


@dataclass
class _Node:
    mathml: str


class _Parser:
    def __init__(self, notation: str):
        compact = notation.strip()
        if not compact or len(compact) > 1000:
            raise MathNotationError("notation_length")
        self.tokens = _TOKEN.findall(compact)
        if "".join(self.tokens) != re.sub(r"\s+", "", compact):
            raise MathNotationError("unsupported_notation_token")
        self.index = 0

    def current(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self, token: str | None = None) -> str:
        value = self.current()
        if value is None or (token is not None and value != token):
            raise MathNotationError("unexpected_notation_structure")
        self.index += 1
        return value

    def expression(self) -> _Node:
        left = self.sum()
        parts = [left.mathml]
        while self.current() in {"=", "<", ">", "<=", ">=", "!=", "≤", "≥", "≠", "∈", "∉"}:
            operator = _OPERATOR.get(self.take(), self.tokens[self.index - 1])
            parts.extend((_mo(operator), self.sum().mathml))
        return _Node("<mrow>" + "".join(parts) + "</mrow>") if len(parts) > 1 else left

    def document(self) -> _Node:
        """A comma-separated line remains one formula review unit."""
        item = self.expression()
        parts = [item.mathml]
        while self.current() == ",":
            self.take(",")
            parts.extend((_mo(","), self.expression().mathml))
        return _Node("<mrow>" + "".join(parts) + "</mrow>") if len(parts) > 1 else item

    def sum(self) -> _Node:
        left = self.product()
        parts = [left.mathml]
        while self.current() in {"+", "-", "−"}:
            operator = _OPERATOR.get(self.take(), self.tokens[self.index - 1])
            parts.extend((f"<mo>{operator}</mo>", self.product().mathml))
        return _Node("<mrow>" + "".join(parts) + "</mrow>") if len(parts) > 1 else left

    def product(self) -> _Node:
        left = self.power()
        parts = [left.mathml]
        while self.current() in {"*", "×", "·", "/", "÷"}:
            operator = self.take()
            right = self.power()
            if operator in {"/", "÷"}:
                left = _Node(f"<mfrac>{left.mathml}{right.mathml}</mfrac>")
                parts = [left.mathml]
            else:
                parts.extend(("<mo>×</mo>", right.mathml))
                left = _Node("<mrow>" + "".join(parts) + "</mrow>")
        return left

    def power(self) -> _Node:
        base = self.primary()
        if self.current() in {"^", "_"}:
            kind = self.take()
            # OCR writes a fractional exponent as ``^(3/2)``.  Those
            # parentheses establish parsing precedence only; they are not
            # spoken mathematical content.
            if self.current() == "(":
                self.take("(")
                exponent = self.expression()
                self.take(")")
            else:
                exponent = self.primary()
            tag = "msup" if kind == "^" else "msub"
            return _Node(f"<{tag}>{base.mathml}{exponent.mathml}</{tag}>")
        return base

    def primary(self) -> _Node:
        token = self.current()
        if token is None:
            raise MathNotationError("missing_operand")
        if token in {"-", "−"}:
            self.take()
            operand = self.primary()
            return _Node(f"<mrow><mo>−</mo>{operand.mathml}</mrow>")
        if token in {"\\sqrt", "√"}:
            self.take()
            degree = None
            if self.current() == "[":
                self.take("["); degree = self.expression(); self.take("]")
            opening, closing = ("{", "}") if self.current() == "{" else ("(", ")")
            self.take(opening); radicand = self.expression(); self.take(closing)
            return _Node(f"<mroot>{radicand.mathml}{degree.mathml}</mroot>" if degree else f"<msqrt>{radicand.mathml}</msqrt>")
        if token == "(":
            self.take("("); item = self.expression(); self.take(")")
            if item.mathml.startswith("<mrow><mo>−</mo>"):
                return item
            return _Node(f"<mfenced>{item.mathml}</mfenced>")
        if token == "{":
            self.take("{"); item = self.expression(); self.take("}")
            return _Node(f"<mfenced>{item.mathml}</mfenced>")
        value = self.take()
        if re.fullmatch(r"\d+(?:[.,]\d+)?", value):
            node = _Node(f"<mn>{_escape(value)}</mn>")
            if self.current() in _UNITS:
                unit = _UNITS[self.take()]
                return _Node(f"<mrow>{node.mathml}<mtext>{unit}</mtext></mrow>")
            return node
        if value == "\\mathbb{":
            letter = self.take(); self.take("}")
            if letter != "R":
                raise MathNotationError("unsupported_blackboard_identifier")
            return _Node("<mi>ℝ</mi>")
        if re.fullmatch(r"[A-Za-zα-ωΑ-Ωℝ]+", value):
            return _Node(f"<mi>{_escape(value)}</mi>")
        raise MathNotationError("unsupported_primary")


def notation_to_mathml(notation: str) -> str:
    parser = _Parser(notation)
    expression = parser.document()
    if parser.current() is not None:
        raise MathNotationError("trailing_notation")
    mathml = f"<math>{expression.mathml}</math>"
    try:
        compile_mathml_candidate(mathml)
    except MathSpeechError as error:
        raise MathNotationError(str(error)) from error
    return mathml


def notation_speech_candidate(notation: str, *, measurement_label: str | None = None) -> tuple[str, str]:
    """Return checked MathML and Turkish speech, optionally with verified context.

    ``measurement_label`` is intentionally teacher-supplied, e.g. ``AB kenarı``.
    A bare number beside a shape must never be upgraded to a side measurement by
    proximity alone.
    """
    mathml = notation_to_mathml(notation)
    spoken = compile_mathml_candidate(mathml)
    if measurement_label:
        label = " ".join(measurement_label.split())
        if not 2 <= len(label) <= 120:
            raise MathNotationError("invalid_measurement_label")
        spoken = f"{label} ölçüsü: {spoken}"
    return mathml, spoken
