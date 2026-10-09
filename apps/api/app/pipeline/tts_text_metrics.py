"""Speech-specific Turkish tokenization shared by TTS screening and diagnostics.

Document OCR metrics must not be reused here: punctuation introduced by ASR is
not spoken, while mathematical operators and Turkish letters must be retained.
"""

from __future__ import annotations

import re
import unicodedata

from .benchmark import levenshtein

_SPOKEN_TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)?|[+−×÷=<>≤≥∈∉∪∩√]", re.UNICODE)


def speech_tokens(value: str) -> list[str]:
    normal = unicodedata.normalize("NFKC", value).replace("İ", "i").replace("I", "ı").casefold()
    return [token.replace("'", "").replace("’", "") for token in _SPOKEN_TOKEN.findall(normal)]


def speech_character_accuracy(expected: str, observed: str) -> float:
    expected_text = " ".join(speech_tokens(expected))
    observed_text = " ".join(speech_tokens(observed))
    return 1 - levenshtein(expected_text, observed_text) / max(len(expected_text), 1)
