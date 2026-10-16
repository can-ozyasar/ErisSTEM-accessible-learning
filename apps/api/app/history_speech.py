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
TURKISH_LETTER_NAMES = {
    "A": "a", "B": "be", "C": "ce", "Ç": "çe", "D": "de", "E": "e",
    "F": "fe", "G": "ge", "Ğ": "yumuşak ge", "H": "he", "I": "ı",
    "İ": "i", "J": "je", "K": "ke", "L": "le", "M": "me", "N": "ne",
    "O": "o", "Ö": "ö", "P": "pe", "R": "re", "S": "se", "Ş": "şe",
    "T": "te", "U": "u", "Ü": "ü", "V": "ve", "Y": "ye", "Z": "ze",
}


def _spoken_source_label(match: re.Match[str]) -> str:
    return "Kaynak " + TURKISH_LETTER_NAMES[match.group(1)]


def history_spoken_text(text: str) -> str:
    """Preserve display text while expanding only reviewed source-label forms."""
    text = SOURCE_A_OBJECT.sub("A kaynağını", text)
    return SOURCE_BARE_LABEL.sub(_spoken_source_label, text)
