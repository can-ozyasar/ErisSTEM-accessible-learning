"""Private Whisper speech-content gate for the corrected V3 smoke sample."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONTROL = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-tts-finetune-control-v1")
OUTPUT = Path("/kaggle/working/eristem-tts-v3-smoke-asr-v1")
SMOKE_OUTPUT_DIR = "eristem-private-chatterbox-v3-finetune-v2"
EXPECTED = "Bugün tarih dersinde eski uygarlıkları öğreniyoruz."


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-zçğıöşü0-9]+", value.casefold()))


def character_accuracy(expected: str, observed: str) -> float:
    a, b = normalized(expected), normalized(observed)
    previous = list(range(len(b) + 1))
    for index, char in enumerate(a, 1):
        current = [index]
        for offset, other in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[offset] + 1,
                               previous[offset - 1] + (char != other)))
        previous = current
    return max(0.0, 1.0 - previous[-1] / max(1, len(a)))


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE") or not CONTROL.exists():
        raise RuntimeError("Private Kaggle smoke koşusu gerekli")
    clips = [p for p in Path("/kaggle/input").rglob("private-smoke-speech.wav")
             if p.parent.name == SMOKE_OUTPUT_DIR]
    if len(clips) != 1:
        raise RuntimeError("Tek düzeltilmiş smoke ses dosyası bulunamadı")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade",
                    "--force-reinstall", "faster-whisper==1.2.1", "av>=14,<17"], check=True)
    import ctranslate2
    from faster_whisper import WhisperModel

    if not ctranslate2.get_supported_compute_types("cuda"):
        raise RuntimeError("Whisper large-v3 için GPU gerekli")
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    segments, _ = model.transcribe(str(clips[0]), language="tr", task="transcribe",
                                   beam_size=5, vad_filter=True,
                                   condition_on_previous_text=False, without_timestamps=True)
    transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    accuracy = round(character_accuracy(EXPECTED, transcript), 4) if transcript else 0.0
    (OUTPUT / "candidate_transcripts.json").write_text(json.dumps({
        "schema_version": "tts-v3-smoke-transcript-v1", "expected": EXPECTED,
        "observed": transcript, "character_accuracy": accuracy,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "run_metadata.json").write_text(json.dumps({
        "schema_version": "tts-v3-smoke-asr-v1", "audio_sha256": sha256(clips[0]),
        "model": "Whisper large-v3", "language": "tr", "character_accuracy": accuracy,
        "gate_passed": accuracy >= 0.7, "student_publication": "blocked_pending_blind_listening",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
