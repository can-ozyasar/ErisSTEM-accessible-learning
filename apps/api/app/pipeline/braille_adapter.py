"""Translate published literary text with the actual Turkish Liblouis table."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .accessibility_reader import ReadingUnit


class BrailleUnavailable(ValueError):
    pass


class LiteraryBrailleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "literary-braille-v1"
    unit_id: str
    language: str = "tr"
    code: str = "turkish-literary-grade-1"
    engine: str = "liblouis"
    engine_version: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cells: str = Field(min_length=1, max_length=16000)


def translate_verified_literary(unit: ReadingUnit) -> LiteraryBrailleResponse:
    if unit.kind not in {"heading", "paragraph"} or not unit.braille_available:
        raise BrailleUnavailable("unsupported_or_unverified_braille_unit")
    worker = Path(__file__).with_name("braille_liblouis_worker.py")
    try:
        result = subprocess.run(
            [os.getenv("LIBLOUIS_PYTHON", "/usr/bin/python3"), str(worker)],
            input=json.dumps({"text": unit.spoken_text}, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode or len(result.stdout) > 50_000:
            raise BrailleUnavailable("braille_translation_unavailable")
        payload = json.loads(result.stdout)
        cells, version = payload["cells"], payload["engine_version"]
        if not isinstance(cells, str) or not cells or not all("\u2800" <= cell <= "\u28ff" for cell in cells):
            raise BrailleUnavailable("invalid_braille_cells")
        if not isinstance(version, str) or not version:
            raise BrailleUnavailable("invalid_braille_engine_version")
        return LiteraryBrailleResponse(
            unit_id=unit.id,
            engine_version=version,
            source_sha256=hashlib.sha256(unit.spoken_text.encode("utf-8")).hexdigest(),
            cells=cells,
        )
    except (OSError, subprocess.TimeoutExpired, KeyError, ValueError, json.JSONDecodeError) as error:
        raise BrailleUnavailable("braille_translation_unavailable") from error
