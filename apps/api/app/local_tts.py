"""Boundary for the internal, offline Turkish TTS service.

The browser never chooses the text sent to the service.  Student endpoints
resolve an already-reviewed reading-plan unit first, then pass only that text
over Docker's internal network.  Keeping this boundary small also lets us
replace the runtime with a tested fine-tuned model later.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_SPOKEN_TEXT_CHARS = 8_000
MAX_AUDIO_BYTES = 32 * 1024 * 1024


class LocalTtsUnavailable(RuntimeError):
    """The optional local service is disabled, unavailable, or unsafe."""


def local_tts_url() -> str | None:
    """Return an internal-only endpoint when local synthesis was configured."""
    value = os.getenv("LOCAL_TTS_URL", "").strip()
    if not value.startswith("http://"):
        return None
    return value


def synthesize_verified_text(text: str) -> bytes:
    """Request a bounded WAV from Piper without exposing an arbitrary TTS API."""
    endpoint = local_tts_url()
    if endpoint is None or not text.strip() or len(text) > MAX_SPOKEN_TEXT_CHARS:
        raise LocalTtsUnavailable("local_tts_unavailable")
    request = Request(
        endpoint,
        data=json.dumps({"text": text}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "audio/wav"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:  # nosec B310: endpoint is Docker-internal config
            body = response.read(MAX_AUDIO_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as error:
        raise LocalTtsUnavailable("local_tts_unavailable") from error
    # Piper 1.8 currently responds with ``text/html`` despite returning a WAV.
    # Trust the bounded RIFF/WAVE structure, not that incorrect header.  A
    # correctly labelled response still must have the same signature.
    is_wav = len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WAVE"
    if not is_wav or not 44 <= len(body) <= MAX_AUDIO_BYTES:
        raise LocalTtsUnavailable("invalid_local_tts_response")
    return body
