"""Private ASR alignment pilot; retains numeric diagnostics, never transcripts or audio."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

SOURCE = "omersaidd/tts_nisan_kumru_tur"
REVISION = "678712b026da89058feb010886de23983cc8563b"
CONTROL = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-tts-finetune-control-v1")
OUTPUT = Path("/kaggle/working/eristem-tts-alignment-audit-pilot")
MAX_EXAMPLES = 200


def normalize(value: str) -> str:
    value = value.replace("I", "ı").replace("İ", "i").casefold()
    return " ".join(re.findall(r"[a-zçğıöşü0-9]+", value))


def error_rate(reference: str, observed: str) -> float:
    reference, observed = normalize(reference), normalize(observed)
    if not reference:
        raise ValueError("empty_normalized_reference")
    previous = list(range(len(observed) + 1))
    for i, char in enumerate(reference, 1):
        current = [i]
        for j, other in enumerate(observed, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (char != other)))
        previous = current
    return previous[-1] / len(reference)


def quality(wave: np.ndarray, rate: int, text: object) -> bool:
    if wave.ndim != 1 or not len(wave) or rate <= 0 or not np.isfinite(wave).all() or not isinstance(text, str):
        return False
    wave = np.clip(wave, -1, 1)
    seconds = len(wave) / rate
    text = " ".join(text.split())
    rms = float(np.sqrt(np.mean(np.square(wave), dtype=np.float64)))
    rms_dbfs = 20 * math.log10(max(rms, 1e-9))
    frame = max(1, int(rate * 0.04))
    usable = wave[: len(wave) - len(wave) % frame]
    frame_rms = np.sqrt(np.mean(np.square(usable.reshape(-1, frame)), axis=1)) if len(usable) else np.array([0.0])
    active = float(np.mean(frame_rms >= max(rms * 0.18, 10 ** (-48 / 20))))
    return (1.2 <= seconds <= 15 and 4 <= len(text) <= 340 and -42 <= rms_dbfs <= -12
            and float(np.max(np.abs(wave))) <= 0.995 and float(np.mean(np.abs(wave) >= 0.999)) <= 0.001 and active >= 0.55)


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE") or not CONTROL.exists():
        raise RuntimeError("private_kaggle_and_control_required")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "datasets==3.6.0", "librosa>=0.10", "soundfile>=0.12", "faster-whisper==1.2.1", "av>=14,<17"], check=True)
    import ctranslate2
    import librosa
    from datasets import Audio, load_dataset
    from faster_whisper import WhisperModel

    if not ctranslate2.get_supported_compute_types("cuda"):
        raise RuntimeError("cuda_required")
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    dataset = load_dataset(SOURCE, revision=REVISION, split="train", streaming=True).cast_column("audio", Audio(decode=True))
    rows = []
    counts = {"seen": 0, "rejected_acoustic": 0, "asr_failures": 0}
    for index, row in enumerate(dataset):
        counts["seen"] += 1
        if index == 0:
            continue
        try:
            audio = row["audio"]
            samples = np.asarray(audio["array"], dtype=np.float32)
            rate = int(audio["sampling_rate"])
            if samples.ndim == 2:
                samples = samples.mean(axis=1 if samples.shape[0] > samples.shape[1] else 0)
            if not quality(samples, rate, row.get("text")):
                counts["rejected_acoustic"] += 1
                continue
            samples = np.clip(samples, -1, 1)
            wave = librosa.resample(samples, orig_sr=rate, target_sr=16_000) if rate != 16_000 else samples
            segments, _ = model.transcribe(wave, language="tr", task="transcribe", beam_size=5, vad_filter=True, condition_on_previous_text=False, without_timestamps=True)
            observed = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
            if not observed or len(observed) > 8_000:
                raise ValueError("invalid_asr_output")
            transcript = " ".join(row["text"].split())
            rows.append({"source_index": index, "seconds": round(len(samples) / rate, 3),
                         "normalized_text_sha256": hashlib.sha256(normalize(transcript).encode()).hexdigest(),
                         "decoded_audio_sha256": hashlib.sha256(samples.tobytes()).hexdigest(),
                         "asr_character_error_rate": round(error_rate(transcript, observed), 5)})
        except (KeyError, TypeError, ValueError, RuntimeError, OSError):
            counts["asr_failures"] += 1
        if len(rows) >= MAX_EXAMPLES:
            break

    if len(rows) < MAX_EXAMPLES:
        raise RuntimeError("alignment_pilot_incomplete")
    rates = [item["asr_character_error_rate"] for item in rows]
    report = {"schema_version": "tts-alignment-audit-pilot-v1", "source_revision": REVISION,
              "asr_model": "faster-whisper large-v3", "language": "tr", "selection": "first 200 acoustically accepted records; first music item excluded",
              "counts": counts | {"transcribed": len(rows)}, "total_seconds": round(sum(item["seconds"] for item in rows), 2),
              "cer_bands": {"at_most_005": sum(x <= 0.05 for x in rates), "at_most_010": sum(x <= 0.10 for x in rates),
                            "at_most_020": sum(x <= 0.20 for x in rates), "over_020": sum(x > 0.20 for x in rates)},
              "mean_cer": round(float(np.mean(rates)), 5), "median_cer": round(float(np.median(rates)), 5),
              "warning": "ASR disagreements need manual review; do not auto-rewrite transcripts or reject solely from this pilot.",
              "contains_audio_or_transcripts": False}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "run_metadata.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "private-audit-records.json").write_text(json.dumps({"schema_version": "tts-alignment-records-v1", "records": rows}, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
