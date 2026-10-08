"""Kaggle T4: private Turkish STEM TTS synthesis candidate benchmark.

This runner generates private WAV files from a sealed ``tts-gold-v1`` manifest.
It never scores the voice, publishes audio, or decides student release. Human
or ASR-reviewed transcripts are deliberately produced outside this runner and
are scored locally by ``app.pipeline.tts_quality``.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-tts-gold-v1")
OUTPUT = Path("/kaggle/working/eristem-private-tts-chatterbox-v1")
GOLD_FILENAME = "tts-gold-v1.json"
MAX_ITEMS = 200
MAX_UTTERANCE_CHARS = 8_000
ITEM_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class TtsInputError(ValueError):
    """The sealed TTS Gold input does not meet the bounded runner contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(source: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in source.infolist():
        target = (root / member.filename).resolve()
        if not target.is_relative_to(root):
            raise TtsInputError("zip_member_outside_private_input")
    source.extractall(destination)


def resolve_gold() -> Path:
    candidates = list(INPUT.rglob(GOLD_FILENAME))
    if not candidates:
        archives = list(INPUT.rglob("*.zip"))
        if len(archives) != 1:
            raise TtsInputError("expected_one_tts_gold_manifest")
        unpacked = OUTPUT / "input"
        with zipfile.ZipFile(archives[0]) as source:
            safe_extract(source, unpacked)
        candidates = list(unpacked.rglob(GOLD_FILENAME))
    if len(candidates) != 1:
        raise TtsInputError("expected_one_tts_gold_manifest")
    return candidates[0]


def load_gold(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload["items"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise TtsInputError("invalid_tts_gold") from error
    if payload.get("schema_version") != "tts-gold-v1" or not isinstance(items, list):
        raise TtsInputError("invalid_tts_gold_schema")
    if not 1 <= len(items) <= MAX_ITEMS:
        raise TtsInputError("invalid_tts_gold_item_count")
    valid_kinds = {"text", "formula", "table", "chart", "exercise"}
    seen: set[str] = set()
    checked = []
    for item in items:
        if not isinstance(item, dict):
            raise TtsInputError("invalid_tts_gold_item")
        item_id, text, kind = item.get("id"), item.get("expected_spoken_text"), item.get("kind")
        if (
            not isinstance(item_id, str)
            or not item_id
            or not ITEM_ID_PATTERN.fullmatch(item_id)
            or item_id in seen
            or not isinstance(text, str)
            or not text.strip()
            or len(text) > MAX_UTTERANCE_CHARS
            or kind not in valid_kinds
        ):
            raise TtsInputError("invalid_tts_gold_item")
        seen.add(item_id)
        checked.append({"id": item_id, "text": text, "kind": kind})
    return checked


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "chatterbox-tts"], check=True
    )
    import torch
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_required_for_chatterbox_multilingual_benchmark")
    gold_path = resolve_gold()
    items = load_gold(gold_path)
    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda", t3_model="v3")
    audio_dir = OUTPUT / "private-audio"
    audio_dir.mkdir(exist_ok=True)
    records = []
    for position, item in enumerate(items, start=1):
        item_id = str(item["id"])
        print(f"[{position}/{len(items)}] Synthesising: {item_id}")
        started = time.monotonic()
        try:
            waveform = model.generate(str(item["text"]), language_id="tr")
            destination = audio_dir / f"{item_id}.wav"
            ta.save(str(destination), waveform.detach().cpu(), model.sr)
            samples = int(waveform.shape[-1])
            records.append(
                {
                    "id": item_id,
                    "kind": item["kind"],
                    "status": "generated",
                    "duration_seconds": samples / model.sr,
                    "generation_seconds": time.monotonic() - started,
                    "audio_sha256": sha256(destination),
                }
            )
        except (OSError, RuntimeError, ValueError) as error:
            records.append({"id": item_id, "kind": item["kind"], "status": "failed", "error_type": type(error).__name__})
    generated = sum(record["status"] == "generated" for record in records)
    summary = {
        "schema_version": "tts-synthesis-run-v1",
        "candidate": "chatterbox-multilingual-v3",
        "language": "tr",
        "input_private": True,
        "student_publication": "blocked_pending_local_quality_evaluation",
        "items_total": len(records),
        "items_generated": generated,
        "items_failed": len(records) - generated,
        "records": records,
    }
    (OUTPUT / "run_records.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUTPUT / "run_metadata.json").write_text(
        json.dumps(
            {
                "candidate": "chatterbox-multilingual-v3",
                "language": "tr",
                "device": torch.cuda.get_device_name(0),
                "torch_version": torch.__version__,
                "chatterbox_version": importlib.metadata.version("chatterbox-tts"),
                "input_private": True,
                "student_publication": "blocked_pending_local_quality_evaluation",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    # The sealed input may have been unpacked from a Kaggle Dataset archive.
    shutil.rmtree(OUTPUT / "input", ignore_errors=True)
    print(f"Finished: {generated}/{len(records)} private audio samples generated; publication blocked.")


if __name__ == "__main__":
    main()
