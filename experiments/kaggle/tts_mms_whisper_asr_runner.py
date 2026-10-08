"""Kaggle T4: private Whisper screen for the Turkish MMS-TTS candidate.

Transcripts remain a private evaluation artefact.  This runner neither
approves a voice nor produces student-facing content.
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

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-tts-mms-tur-audio-v1")
OUTPUT = Path("/kaggle/working/eristem-private-tts-mms-tur-asr-whisper-large-v3-v1")
INPUT_FILENAME = "tts-asr-input.json"
ASR_MODEL = "large-v3"
ASR_LANGUAGE = "tr"
MAX_ASSETS = 200
MAX_TRANSCRIPT_CHARS = 8_000
ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VALID_KINDS = {"text", "formula", "table", "chart", "exercise"}


class AsrInputError(ValueError):
    """The sealed private audio package failed a structural integrity check."""


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
            raise AsrInputError("zip_member_outside_private_input")
    source.extractall(destination)


def resolve_input_manifest() -> Path:
    candidates = list(INPUT.rglob(INPUT_FILENAME))
    if not candidates:
        archives = list(INPUT.rglob("*.zip"))
        if len(archives) != 1:
            raise AsrInputError("expected_one_tts_asr_input_manifest")
        unpacked = OUTPUT / "input"
        with zipfile.ZipFile(archives[0]) as source:
            safe_extract(source, unpacked)
        candidates = list(unpacked.rglob(INPUT_FILENAME))
    if len(candidates) != 1:
        raise AsrInputError("expected_one_tts_asr_input_manifest")
    return candidates[0]


def load_assets(manifest_path: Path) -> tuple[str, list[dict[str, object]]]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        candidate, assets = payload["candidate"], payload["assets"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise AsrInputError("invalid_tts_asr_input") from error
    if (
        payload.get("schema_version") != "tts-asr-input-v1"
        or not isinstance(candidate, str)
        or not 1 <= len(candidate) <= 100
        or not isinstance(assets, list)
        or not 1 <= len(assets) <= MAX_ASSETS
    ):
        raise AsrInputError("invalid_tts_asr_input_schema")
    root = manifest_path.parent.resolve()
    checked, seen = [], set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise AsrInputError("invalid_tts_asr_asset")
        item_id, kind, relative_path, expected_hash = (
            asset.get("id"), asset.get("kind"), asset.get("audio_path"), asset.get("audio_sha256")
        )
        if (
            not isinstance(item_id, str)
            or not ID_PATTERN.fullmatch(item_id)
            or item_id in seen
            or kind not in VALID_KINDS
            or not isinstance(relative_path, str)
            or not isinstance(expected_hash, str)
            or not SHA256_PATTERN.fullmatch(expected_hash)
        ):
            raise AsrInputError("invalid_tts_asr_asset")
        audio_path = (root / relative_path).resolve()
        if (
            not audio_path.is_relative_to(root)
            or audio_path.name != f"{item_id}.wav"
            or audio_path.suffix.lower() != ".wav"
            or not audio_path.is_file()
            or sha256(audio_path) != expected_hash
        ):
            raise AsrInputError("tts_asr_audio_integrity_mismatch")
        seen.add(item_id)
        checked.append({"id": item_id, "kind": kind, "audio_path": audio_path, "audio_sha256": expected_hash})
    return candidate, checked


def install_asr_runtime() -> None:
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "--force-reinstall",
            "faster-whisper==1.2.1", "av>=14,<17",
        ],
        check=True,
    )


def transcript(model, audio_path: Path) -> str:
    segments, _ = model.transcribe(
        str(audio_path), language=ASR_LANGUAGE, task="transcribe", beam_size=5,
        vad_filter=True, condition_on_previous_text=False, without_timestamps=True,
    )
    return " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    install_asr_runtime()
    import ctranslate2
    from faster_whisper import WhisperModel

    if not ctranslate2.get_supported_compute_types("cuda"):
        raise RuntimeError("cuda_required_for_tts_asr_screen")
    manifest_path = resolve_input_manifest()
    candidate, assets = load_assets(manifest_path)
    model = WhisperModel(ASR_MODEL, device="cuda", compute_type="float16")
    results, records = [], []
    for position, asset in enumerate(assets, start=1):
        item_id = str(asset["id"])
        print(f"[{position}/{len(assets)}] Transcribing: {item_id}")
        started = time.monotonic()
        try:
            observed = transcript(model, Path(asset["audio_path"]))
            if not observed or len(observed) > MAX_TRANSCRIPT_CHARS:
                raise AsrInputError("empty_or_oversized_asr_transcript")
            results.append({"id": item_id, "observed_spoken_text": observed})
            records.append({
                "id": item_id, "kind": asset["kind"], "status": "transcribed",
                "audio_sha256": asset["audio_sha256"], "transcription_seconds": time.monotonic() - started,
            })
        except (AsrInputError, OSError, RuntimeError, ValueError) as error:
            records.append({
                "id": item_id, "kind": asset["kind"], "status": "failed",
                "audio_sha256": asset["audio_sha256"], "error_type": type(error).__name__,
            })
    (OUTPUT / "candidate_transcripts.json").write_text(
        json.dumps({"schema_version": "tts-candidate-v1", "candidate": candidate, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    completed = sum(record["status"] == "transcribed" for record in records)
    (OUTPUT / "run_records.json").write_text(
        json.dumps({
            "schema_version": "tts-asr-run-v1", "candidate": candidate, "asr_model": ASR_MODEL,
            "items_total": len(records), "items_transcribed": completed, "items_failed": len(records) - completed,
            "records": records,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT / "run_metadata.json").write_text(
        json.dumps({
            "candidate": candidate, "asr_model": ASR_MODEL, "asr_language": ASR_LANGUAGE, "device": "cuda",
            "faster_whisper_version": importlib.metadata.version("faster-whisper"),
            "ctranslate2_version": importlib.metadata.version("ctranslate2"), "input_private": True,
            "student_publication": "blocked_pending_local_tts_quality_evaluation",
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    shutil.rmtree(OUTPUT / "input", ignore_errors=True)
    print(f"Finished: {completed}/{len(records)} private ASR transcripts produced; publication blocked.")


if __name__ == "__main__":
    main()
