"""Boundary for the internal, offline Turkish TTS service.

Lesson-audio endpoints resolve an already-reviewed reading-plan unit first.
The separate, development-only interface-exploration endpoint accepts short
UI labels from the browser but never stores them as reviewed lesson audio.
Both paths send text only over Docker's internal network.
"""

from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_SPOKEN_TEXT_CHARS = 8_000
MAX_AUDIO_BYTES = 32 * 1024 * 1024
VOICE_CACHE_VERSION = "piper-tr_TR-dfki-medium-v1"


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


def _cache_root() -> Path | None:
    """Return the private volume for reviewed audio only.

    The filename is a salted content digest; source text is never written as a
    filename or sidecar.  If the volume is unavailable, synthesis still works.
    """
    value = os.getenv("LOCAL_TTS_CACHE_ROOT", "").strip()
    if not value:
        return None
    try:
        root = Path(value).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root
    except OSError:
        return None


def synthesize_cached_verified_text(text: str) -> bytes:
    """Synthesize reviewed text once, then reuse its local WAV across sessions."""
    root = _cache_root()
    if root is None:
        return synthesize_verified_text(text)
    digest = hashlib.sha256(f"{VOICE_CACHE_VERSION}\0{text}".encode("utf-8")).hexdigest()
    target = root / f"{digest}.wav"
    try:
        cached = target.read_bytes()
        if len(cached) >= 44 and cached[:4] == b"RIFF" and cached[8:12] == b"WAVE":
            return cached
        target.unlink(missing_ok=True)
    except OSError:
        pass
    audio = synthesize_verified_text(text)
    try:
        with NamedTemporaryFile(dir=root, prefix=".audio-", suffix=".tmp", delete=False) as temp:
            temp.write(audio)
            temporary = Path(temp.name)
        temporary.replace(target)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except UnboundLocalError:
            pass
    return audio


def synthesize_history_text(text: str) -> bytes:
    """Prepare history pronunciation and speak the entire turn in one voice."""
    from .history_speech import history_spoken_text

    return synthesize_cached_verified_text(history_spoken_text(text))
