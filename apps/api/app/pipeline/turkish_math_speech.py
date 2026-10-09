"""Deterministic Turkish speech plans for already-verified MathML.

This is deliberately a small compiler, not an OCR post-processor or an LLM
prompt.  It accepts a bounded MathML subset only after the formula has passed
the regular release-quality gate.  Unsupported notation is rejected so that a
teacher can supply a verified reading instead of a student hearing a guess.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .type_specific_accessibility import FormulaAccessibility, require_release_quality

RULESET_VERSION = "turkish-math-speech-v1"
MAX_MATHML_BYTES = 8_000
MAX_NODES = 120
MAX_DEPTH = 16
_ALLOWED_TAGS = {"math", "mrow", "mi", "mn", "mo", "msup", "msub", "mfrac", "msqrt", "mroot", "mfenced", "mtext"}
_LEAF_TAGS = {"mi", "mn", "mo", "mtext"}
_MATHML_NAMESPACES = {"", "http://www.w3.org/1998/Math/MathML"}
_IDENTIFIER = re.compile(r"^[\wαβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]+$", re.UNICODE)
_NUMBER = re.compile(r"^\d+(?:[,.]\d+)?$")

_OPERATORS = {
    "+": "artı", "-": "eksi", "−": "eksi", "=": "eşittir", "×": "çarpı", "·": "çarpı",
    "⋅": "çarpı", "/": "bölü", "<": "küçüktür", ">": "büyüktür", "≤": "küçük veya eşittir",
    "≥": "büyük veya eşittir", "≠": "eşit değildir", "∈": "elemanıdır", "∉": "elemanı değildir",
    "∪": "birleşim", "∩": "kesişim", "⊆": "alt kümesidir", "⊂": "öz alt kümesidir",
    "∅": "boş küme", "(": "aç parantez", ")": "kapa parantez", "[": "aç köşeli parantez",
    "]": "kapa köşeli parantez", "{": "aç küme parantezi", "}": "kapa küme parantezi", "!": "faktöriyel",
}
_GREEK = {"α": "alfa", "β": "beta", "γ": "gama", "δ": "delta", "π": "pi", "θ": "teta", "λ": "lambda", "μ": "mü", "σ": "sigma", "φ": "fi", "ω": "omega"}
_ONES = ("", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz")
_TENS = ("", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan")


class TurkishMathSpeechPlan(BaseModel):
    """Versioned, source-bound instruction for a TTS adapter."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["turkish-math-speech-plan-v1"] = "turkish-math-speech-plan-v1"
    ruleset_version: Literal["turkish-math-speech-v1"] = RULESET_VERSION
    source_mathml_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    spoken_text: str = Field(min_length=1, max_length=5_000)
    reading_mode: Literal["detailed"] = "detailed"
    requires_teacher_review_for_unsupported_notation: bool = False


class MathSpeechError(ValueError):
    """The verified formula uses notation outside the fail-closed subset."""


@dataclass(frozen=True)
class _Rendered:
    text: str
    compound: bool = False


def _tag(element: ET.Element) -> str:
    raw = element.tag
    if not isinstance(raw, str):
        raise MathSpeechError("invalid_mathml_tag")
    if raw.startswith("{"):
        namespace, local = raw[1:].split("}", 1)
        if namespace not in _MATHML_NAMESPACES:
            raise MathSpeechError("unsupported_mathml_namespace")
        return local
    return raw


def _bounded_tree(mathml: str) -> ET.Element:
    encoded = mathml.encode("utf-8")
    if not 13 <= len(encoded) <= MAX_MATHML_BYTES or "<!" in mathml:
        raise MathSpeechError("invalid_mathml_length_or_declaration")
    try:
        root = ET.fromstring(mathml)
    except ET.ParseError as error:
        raise MathSpeechError("malformed_mathml") from error
    if _tag(root) != "math":
        raise MathSpeechError("mathml_root_required")
    seen = 0

    def visit(node: ET.Element, depth: int) -> None:
        nonlocal seen
        seen += 1
        if seen > MAX_NODES or depth > MAX_DEPTH:
            raise MathSpeechError("mathml_complexity_limit")
        name = _tag(node)
        if name not in _ALLOWED_TAGS or node.attrib:
            raise MathSpeechError("unsupported_mathml_construct")
        if node.tail and not node.tail.isspace():
            raise MathSpeechError("unexpected_mathml_text")
        children = list(node)
        if name in _LEAF_TAGS:
            if children:
                raise MathSpeechError("invalid_mathml_leaf")
        elif node.text and not node.text.isspace():
            raise MathSpeechError("unexpected_mathml_text")
        for child in children:
            visit(child, depth + 1)

    visit(root, 1)
    return root


def _integer_words(number: int) -> str:
    if number == 0:
        return "sıfır"
    if not 0 < number < 1_000_000_000:
        raise MathSpeechError("number_out_of_supported_range")

    def below_thousand(value: int) -> str:
        parts: list[str] = []
        hundreds, value = divmod(value, 100)
        if hundreds:
            parts.append("yüz" if hundreds == 1 else f"{_ONES[hundreds]} yüz")
        tens, ones = divmod(value, 10)
        if tens:
            parts.append(_TENS[tens])
        if ones:
            parts.append(_ONES[ones])
        return " ".join(parts)

    millions, remainder = divmod(number, 1_000_000)
    thousands, below = divmod(remainder, 1_000)
    parts: list[str] = []
    if millions:
        parts.append("bir milyon" if millions == 1 else f"{below_thousand(millions)} milyon")
    if thousands:
        parts.append("bin" if thousands == 1 else f"{below_thousand(thousands)} bin")
    if below:
        parts.append(below_thousand(below))
    return " ".join(parts)


def _number_words(value: str) -> str:
    if not _NUMBER.fullmatch(value):
        raise MathSpeechError("unsupported_number")
    integer, separator, decimal = value.replace(",", ".").partition(".")
    rendered = _integer_words(int(integer))
    if separator:
        rendered += " virgül " + " ".join(_ONES[int(digit)] for digit in decimal)
    return rendered


def _leaf(node: ET.Element, name: str) -> _Rendered:
    value = " ".join((node.text or "").split())
    if not value:
        raise MathSpeechError("empty_mathml_leaf")
    if name == "mn":
        return _Rendered(_number_words(value))
    if name == "mo":
        try:
            return _Rendered(_OPERATORS[value])
        except KeyError as error:
            raise MathSpeechError("unsupported_math_operator") from error
    if name == "mi":
        if not _IDENTIFIER.fullmatch(value):
            raise MathSpeechError("unsupported_math_identifier")
        return _Rendered(_GREEK.get(value.casefold(), value))
    # mtext is deliberately narrow: prose annotations must be reviewed upstream.
    if len(value) > 80 or any(character in "<>\\{}" for character in value):
        raise MathSpeechError("unsupported_math_text")
    return _Rendered(value)


def _group(rendered: _Rendered) -> str:
    return f"aç parantez {rendered.text} kapa parantez" if rendered.compound else rendered.text


def _render(node: ET.Element) -> _Rendered:
    name = _tag(node)
    children = list(node)
    if name in _LEAF_TAGS:
        return _leaf(node, name)
    if name in {"math", "mrow"}:
        if not children:
            raise MathSpeechError("empty_mathml_group")
        return _Rendered(" ".join(_render(child).text for child in children), len(children) > 1)
    if name == "mfenced":
        if not children:
            raise MathSpeechError("empty_fenced_expression")
        return _Rendered(f"aç parantez {' '.join(_render(child).text for child in children)} kapa parantez", True)
    if name == "mfrac":
        if len(children) != 2:
            raise MathSpeechError("invalid_fraction")
        numerator, denominator = (_render(child) for child in children)
        return _Rendered(f"{_group(numerator)} bölü {_group(denominator)}", True)
    if name == "msqrt":
        if len(children) != 1:
            raise MathSpeechError("invalid_square_root")
        return _Rendered(f"karekök içinde {_render(children[0]).text}", True)
    if name == "mroot":
        if len(children) != 2:
            raise MathSpeechError("invalid_root")
        radicand, degree = (_render(child) for child in children)
        return _Rendered(f"{_group(degree)} dereceden kök içinde {_group(radicand)}", True)
    if name == "msup":
        if len(children) != 2:
            raise MathSpeechError("invalid_superscript")
        base, exponent = (_render(child) for child in children)
        if exponent.text == "iki":
            suffix = "karesi"
        elif exponent.text == "üç":
            suffix = "küpü"
        else:
            suffix = f"üzeri {_group(exponent)}"
        return _Rendered(f"{_group(base)} {suffix}", True)
    if name == "msub":
        if len(children) != 2:
            raise MathSpeechError("invalid_subscript")
        base, subscript = (_render(child) for child in children)
        return _Rendered(f"{_group(base)} alt indis {_group(subscript)}", True)
    raise MathSpeechError("unsupported_mathml_construct")


def turkish_math_speech_plan(formula: FormulaAccessibility) -> TurkishMathSpeechPlan:
    """Compile verified MathML to a detailed Turkish reading, or reject it.

    Calling this does not publish a formula or synthesize audio.  It merely
    creates a deterministic candidate reading for the normal review/release
    workflow.
    """
    require_release_quality(formula.quality)
    spoken_text = compile_mathml_candidate(formula.mathml)
    return TurkishMathSpeechPlan(
        source_mathml_sha256=hashlib.sha256(formula.mathml.encode("utf-8")).hexdigest(),
        spoken_text=spoken_text,
    )


def compile_mathml_candidate(mathml: str) -> str:
    """Teacher-only preview; compiling a candidate never publishes it."""
    return _render(_bounded_tree(mathml)).text
