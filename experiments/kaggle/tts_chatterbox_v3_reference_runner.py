"""Kaggle T4: private Turkish STEM TTS, Chatterbox V3 reference-voice test.

The runner streams only a bounded search window from a source-pinned,
single-speaker dataset to select one technically usable reference clip.  It
then creates private audio for the sealed Gold set.  It does not fine-tune a
model, inspect source transcripts, score quality, or publish student audio.
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
OUTPUT = Path("/kaggle/working/eristem-private-tts-chatterbox-v3-reference-v1")
GOLD_FILENAME = "tts-gold-v1.json"
SOURCE_DATASET = "omersaidd/tts_nisan_kumru_tur"
SOURCE_REVISION = "678712b026da89058feb010886de23983cc8563b"
SOURCE_REFERENCE = "target-voice-001"
CANDIDATE = "chatterbox-multilingual-v3-reference-target-voice-001-v1"
CHATTERBOX_VERSION = "0.1.7"
REFERENCE_SAMPLE_RATE = 24_000
MIN_REFERENCE_SECONDS = 8.0
MAX_REFERENCE_SECONDS = 12.0
MAX_REFERENCE_CANDIDATES = 128
MAX_ITEMS = 200
MAX_UTTERANCE_CHARS = 8_000
ITEM_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class TtsInputError(ValueError):
    """A bounded private input or source reference contract failed."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(source: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in source.infolist():
        if not (root / member.filename).resolve().is_relative_to(root):
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


def install_runtime() -> None:
    """Use a known API release and remove only the incompatible optional wheel."""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", f"chatterbox-tts=={CHATTERBOX_VERSION}", "datasets>=3.0,<4"],
        check=True,
    )
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "--yes", "torchvision"], check=True)


def load_v3(factory):
    """Keep V3 explicit: omitting this parameter would silently benchmark V2."""
    return factory.from_pretrained(device="cuda", t3_model="v3")


def viable_reference_waveform(audio: object, torch, torchaudio):
    """Return a clean, mono 24 kHz reference waveform or ``None``.

    No transcription field is read during selection.  This is a technical
    filter, not a claim of semantic or speaker-quality validation.
    """
    if not isinstance(audio, dict):
        return None
    samples, sample_rate = audio.get("array"), audio.get("sampling_rate")
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        return None
    try:
        waveform = torch.as_tensor(samples, dtype=torch.float32)
    except (RuntimeError, TypeError, ValueError):
        return None
    if waveform.ndim == 2:
        waveform = waveform.mean(dim=1)
    if waveform.ndim != 1 or not waveform.numel():
        return None
    duration = waveform.numel() / sample_rate
    if not MIN_REFERENCE_SECONDS <= duration <= MAX_REFERENCE_SECONDS:
        return None
    peak = float(waveform.abs().max())
    rms = float(waveform.square().mean().sqrt())
    clipping = float((waveform.abs() >= 0.999).float().mean())
    if not 0.005 <= rms <= 0.5 or peak <= 0.02 or clipping > 0.002:
        return None
    if sample_rate != REFERENCE_SAMPLE_RATE:
        waveform = torchaudio.functional.resample(waveform, sample_rate, REFERENCE_SAMPLE_RATE)
    return waveform.unsqueeze(0)


def select_reference(dataset, torch, torchaudio) -> tuple[object, int]:
    """Select the first technically valid item from a bounded pinned stream."""
    for position, row in enumerate(dataset, start=1):
        if position > MAX_REFERENCE_CANDIDATES:
            break
        if not isinstance(row, dict):
            continue
        waveform = viable_reference_waveform(row.get("audio"), torch, torchaudio)
        if waveform is not None:
            return waveform, position
    raise TtsInputError("no_technically_valid_reference_in_bounded_source_window")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    install_runtime()
    import torch
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    from datasets import load_dataset

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_required_for_chatterbox_v3_reference_benchmark")
    gold_path = resolve_gold()
    items = load_gold(gold_path)
    source = load_dataset(SOURCE_DATASET, split="train", streaming=True, revision=SOURCE_REVISION)
    reference_waveform, source_position = select_reference(source, torch, ta)
    reference_path = OUTPUT / "private-reference.wav"
    ta.save(str(reference_path), reference_waveform, REFERENCE_SAMPLE_RATE)
    model = load_v3(ChatterboxMultilingualTTS)
    audio_dir = OUTPUT / "private-audio"
    audio_dir.mkdir(exist_ok=True)
    records = []
    for position, item in enumerate(items, start=1):
        item_id = str(item["id"])
        print(f"[{position}/{len(items)}] Synthesising: {item_id}")
        started = time.monotonic()
        try:
            waveform = model.generate(
                str(item["text"]), language_id="tr", audio_prompt_path=str(reference_path)
            )
            destination = audio_dir / f"{item_id}.wav"
            ta.save(str(destination), waveform.detach().cpu(), model.sr)
            records.append({
                "id": item_id,
                "kind": item["kind"],
                "status": "generated",
                "duration_seconds": int(waveform.shape[-1]) / model.sr,
                "generation_seconds": time.monotonic() - started,
                "audio_sha256": sha256(destination),
            })
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            records.append({"id": item_id, "kind": item["kind"], "status": "failed", "error_type": type(error).__name__})
    generated = sum(record["status"] == "generated" for record in records)
    reference_metadata = {
        "source_dataset": SOURCE_DATASET,
        "source_revision": SOURCE_REVISION,
        "source_reference": SOURCE_REFERENCE,
        "selection": "first-technically-valid-reference-in-bounded-stream-v1",
        "candidates_scanned": min(source_position, MAX_REFERENCE_CANDIDATES),
        "reference_duration_seconds": int(reference_waveform.shape[-1]) / REFERENCE_SAMPLE_RATE,
        "reference_audio_sha256": sha256(reference_path),
    }
    summary = {
        "schema_version": "tts-synthesis-run-v1",
        "candidate": CANDIDATE,
        "language": "tr",
        "input_private": True,
        "student_publication": "blocked_pending_local_quality_evaluation",
        "reference": reference_metadata,
        "items_total": len(records),
        "items_generated": generated,
        "items_failed": len(records) - generated,
        "records": records,
    }
    (OUTPUT / "run_records.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "run_metadata.json").write_text(json.dumps({
        "candidate": CANDIDATE,
        "language": "tr",
        "device": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
        "chatterbox_version": importlib.metadata.version("chatterbox-tts"),
        "source_dataset": SOURCE_DATASET,
        "source_revision": SOURCE_REVISION,
        "source_reference": SOURCE_REFERENCE,
        "input_private": True,
        "student_publication": "blocked_pending_local_quality_evaluation",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(OUTPUT / "input", ignore_errors=True)
    print(f"Finished: {generated}/{len(records)} private audio samples generated; publication blocked.")


if __name__ == "__main__":
    main()
