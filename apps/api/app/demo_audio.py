"""Resolve private demonstration audio only for its exact source and text."""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

MODEL_SHA256 = "8ec3a3312b9586a8650c38d2c8e8e8b6214851f13afbaa935ed4c9d598af8503"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


@lru_cache(maxsize=8)
def _source_digest(path: Path, size: int, mtime_ns: int) -> str:
    return _sha256_file(path)


def _resolve_at(root: Path, kind: str, item_id: str, text: str, source: Path | None) -> bytes | None:
    try:
        manifest_path = root / "index.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest.get("schema_version") != "v5-demo-installed-v1"
                or manifest.get("model_sha256") != MODEL_SHA256
                or manifest.get("runtime_enabled") is not True
                or manifest.get("requires_listening_review") is not False):
            return None
        if kind != "interface":
            if source is None:
                return None
            expected_source = manifest["source_sha256"][kind]
            stat = source.stat()
            if _source_digest(source, stat.st_size, stat.st_mtime_ns) != expected_source:
                return None
        entries = manifest["items"]
        matches = [row for row in entries if row.get("kind") == kind and row.get("id") == item_id]
        if len(matches) != 1:
            return None
        row = matches[0]
        if row["spoken_text_sha256"] != hashlib.sha256(text.encode("utf-8")).hexdigest():
            return None
        path = (root / row["filename"]).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size != row["bytes"] or _sha256_file(path) != row["audio_sha256"]:
            return None
        audio = path.read_bytes()
        return audio if len(audio) >= 44 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE" else None
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def resolve_demo_audio(kind: str, item_id: str, text: str, source: Path | None = None) -> bytes | None:
    """Resolve only exact text and, for book content, the matching source PDF."""
    if kind not in {"history", "question", "interface"}:
        return None
    for variable in ("LOCAL_TTS_DEMO_ROOT", "LOCAL_TTS_DEMO_EXTRA_ROOT"):
        configured = os.getenv(variable, "").strip()
        if configured:
            audio = _resolve_at(Path(configured).resolve(), kind, item_id, text, source)
            if audio is not None:
                return audio
    return None


def resolve_demo_interface(text: str) -> bytes | None:
    """Only explicitly generated, exact UI phrases can match; user text is never stored."""
    return resolve_demo_audio("interface", hashlib.sha256(text.encode("utf-8")).hexdigest(), text)
