"""Source-label speech rendering, separate from the printed history text.

Only observed, unambiguous cases are changed. Do not guess how arbitrary
apostrophes, initials, foreign names or multiple-choice labels are spoken.
"""

from __future__ import annotations

import re

SOURCE_A_OBJECT = re.compile(r"\bKaynak\s+A['’]yı\b")
# This deliberately matches only a *bare* source label.  A suffix such as
# ``Kaynak H'den`` has Turkish morphologic information and is left for a
# reviewed rule rather than guessed by a broad replacement.
SOURCE_BARE_LABEL = re.compile(r"\bKaynak\s+([A-ZÇĞİÖŞÜ])\b(?!['’])")
BEFORE_COMMON_ERA = re.compile(r"\bMÖ\b")
ROMAN_CENTURY = re.compile(r"\b([IVXLCDM]+)\.\s*(yüzyıl(?:[a-zçğıöşü]+)?)\b")
MUSEUM_NAME = "Metropolitan Art Museum"
SPOKEN_MUSEUM_NAME = "Metropoliten Art Müziyum"
CENTURY_ORDINALS = {
    1: "birinci", 2: "ikinci", 3: "üçüncü", 4: "dördüncü", 5: "beşinci",
    6: "altıncı", 7: "yedinci", 8: "sekizinci", 9: "dokuzuncu",
    10: "onuncu", 11: "on birinci", 12: "on ikinci", 13: "on üçüncü",
    14: "on dördüncü", 15: "on beşinci", 16: "on altıncı",
    17: "on yedinci", 18: "on sekizinci", 19: "on dokuzuncu",
    20: "yirminci", 21: "yirmi birinci",
}
TURKISH_LETTER_NAMES = {
    "A": "a", "B": "be", "C": "ce", "Ç": "çe", "D": "de", "E": "e",
    "F": "fe", "G": "ge", "Ğ": "yumuşak ge", "H": "he", "I": "ı",
    "İ": "i", "J": "je", "K": "ke", "L": "le", "M": "me", "N": "ne",
    "O": "o", "Ö": "ö", "P": "pe", "R": "re", "S": "se", "Ş": "şe",
    "T": "te", "U": "u", "Ü": "ü", "V": "ve", "Y": "ye", "Z": "ze",
}


def _spoken_source_label(match: re.Match[str]) -> str:
    return "Kaynak " + TURKISH_LETTER_NAMES[match.group(1)]


def _roman_value(value: str) -> int:
    numerals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    previous = 0
    for symbol in reversed(value):
        current = numerals[symbol]
        total += -current if current < previous else current
        previous = current
    return total


def _canonical_roman(number: int) -> str:
    digits = ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    result = ""
    for amount, symbol in digits:
        count, number = divmod(number, amount)
        result += symbol * count
    return result


def _spoken_century(match: re.Match[str]) -> str:
    roman = match.group(1).upper()
    value = _roman_value(roman)
    ordinal = CENTURY_ORDINALS.get(value)
    if ordinal is None or roman != _canonical_roman(value):
        return match.group(0)
    return f"{ordinal} {match.group(2)}"


def history_spoken_text(text: str) -> str:
    """Create Turkish TTS text separately from the unmodified source display."""
    text = SOURCE_A_OBJECT.sub("A kaynağını", text)
    text = SOURCE_BARE_LABEL.sub(_spoken_source_label, text)
    text = BEFORE_COMMON_ERA.sub("Milattan önce", text)
    text = ROMAN_CENTURY.sub(_spoken_century, text)
    return text.replace(MUSEUM_NAME, SPOKEN_MUSEUM_NAME)
