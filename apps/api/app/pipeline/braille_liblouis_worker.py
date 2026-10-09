"""Isolated system-Python bridge for the distribution's Liblouis binding.

Only an already verified, bounded literary-text unit is accepted on stdin.
The installed Turkish Grade 1 table is checked through a back translation;
unsupported characters fail closed instead of yielding misleading cells.
"""

from __future__ import annotations

import json
import sys
import unicodedata

MAX_TEXT_CHARS = 8000
TABLE = ["tr-g1.ctb"]


def main() -> int:
    try:
        import louis

        request = json.load(sys.stdin)
        text = request.get("text")
        if not isinstance(text, str) or not text or len(text) > MAX_TEXT_CHARS:
            raise ValueError("invalid_braille_source")
        if any(unicodedata.category(char).startswith("C") and char not in "\n\t" for char in text):
            raise ValueError("invalid_braille_source")
        # A literary table is not a mathematics Braille code. A reversible
        # glyph mapping alone would still misrepresent a mathematical symbol.
        if any(unicodedata.category(char).startswith("S") for char in text):
            raise ValueError("math_or_symbol_requires_specialized_braille")
        louis.checkTable(TABLE)
        dots = louis.translateString(TABLE, text, mode=louis.dotsIO)
        if not dots or any(ord(char) >> 8 != 0x80 for char in dots):
            raise ValueError("invalid_braille_dots")
        if louis.backTranslateString(TABLE, dots, mode=louis.dotsIO) != text:
            raise ValueError("braille_roundtrip_mismatch")
        cells = "".join(chr(0x2800 | (ord(char) & 0xFF)) for char in dots)
        print(json.dumps({"cells": cells, "engine_version": louis.version()}, ensure_ascii=False))
        return 0
    except (ImportError, KeyError, TypeError, ValueError, RuntimeError):
        print(json.dumps({"error": "braille_translation_unavailable"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
