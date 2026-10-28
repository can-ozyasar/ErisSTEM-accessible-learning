"""Audit the complete permitted source on private Kaggle; output aggregates only."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np

SOURCE_DATASET = "omersaidd/tts_nisan_kumru_tur"
SOURCE_REVISION = "678712b026da89058feb010886de23983cc8563b"
CONTROL_INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-tts-finetune-control-v1")
OUTPUT = Path("/kaggle/working/eristem-tts-corpus-audit-v1")


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE") or not CONTROL_INPUT.exists():
        raise RuntimeError("private_kaggle_and_control_required")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "datasets==3.6.0", "soundfile>=0.12", "librosa>=0.10"], check=True)
    from datasets import Audio, load_dataset

    dataset = load_dataset(SOURCE_DATASET, revision=SOURCE_REVISION, split="train", streaming=True)
    dataset = dataset.cast_column("audio", Audio(decode=True))
    counts: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    durations: Counter[str] = Counter()
    text_lengths: Counter[str] = Counter()
    audio_hashes: set[str] = set()
    text_hashes: set[str] = set()
    seconds_all = seconds_accepted = seconds_reference = 0.0
    for index, row in enumerate(dataset):
        counts["seen"] += 1
        if index == 0:
            rejected["known_first_music"] += 1
            continue
        try:
            audio = row["audio"]
            samples = np.asarray(audio["array"], dtype=np.float32)
            rate = int(audio["sampling_rate"])
            if samples.ndim == 2:
                samples = samples.mean(axis=1 if samples.shape[0] > samples.shape[1] else 0)
            if samples.ndim != 1 or rate <= 0 or not len(samples) or not np.isfinite(samples).all():
                raise ValueError("invalid_audio")
            samples = np.clip(samples, -1.0, 1.0)
            duration = len(samples) / rate
            seconds_all += duration
            durations["under_1_2" if duration < 1.2 else "1_2_to_6" if duration < 6 else "6_to_15" if duration <= 15 else "over_15"] += 1
            text = row.get("text")
            if not isinstance(text, str):
                raise ValueError("invalid_text")
            normalized = " ".join(text.split())
            length = len(normalized)
            text_lengths["under_4" if length < 4 else "4_to_80" if length <= 80 else "81_to_160" if length <= 160 else "161_to_340" if length <= 340 else "over_340"] += 1
            rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64)))
            rms_dbfs = 20 * math.log10(max(rms, 1e-9))
            peak = float(np.max(np.abs(samples)))
            clip_fraction = float(np.mean(np.abs(samples) >= 0.999))
            frame = max(1, int(rate * 0.04))
            usable = samples[: len(samples) - len(samples) % frame]
            frame_rms = np.sqrt(np.mean(np.square(usable.reshape(-1, frame)), axis=1)) if len(usable) else np.array([0.0])
            active_fraction = float(np.mean(frame_rms >= max(rms * 0.18, 10 ** (-48 / 20))))
            reasons = []
            if not 1.2 <= duration <= 15.0: reasons.append("duration")
            if not 4 <= length <= 340: reasons.append("text_length")
            if not -42.0 <= rms_dbfs <= -12.0: reasons.append("rms")
            if peak > 0.995: reasons.append("peak")
            if clip_fraction > 0.001: reasons.append("clipping")
            if active_fraction < 0.55: reasons.append("activity")
            if reasons:
                counts["rejected_quality"] += 1
                rejected.update(reasons)
                continue
            counts["accepted_quality"] += 1
            seconds_accepted += duration
            audio_hash = hashlib.sha256(samples.tobytes()).digest()
            text_hash = hashlib.sha256(normalized.casefold().encode("utf-8")).digest()
            if audio_hash in audio_hashes: counts["exact_audio_duplicates"] += 1
            if text_hash in text_hashes: counts["exact_normalized_text_duplicates"] += 1
            audio_hashes.add(audio_hash)
            text_hashes.add(text_hash)
            if duration >= 6:
                counts["reference_eligible"] += 1
                seconds_reference += duration
        except (KeyError, TypeError, ValueError, OSError, OverflowError):
            counts["invalid_records"] += 1
            rejected["invalid_record"] += 1
        if counts["seen"] % 500 == 0:
            print(f"İncelenen kayıt sayısı: {counts['seen']}", flush=True)

    if counts["seen"] == 0 or counts["accepted_quality"] == 0:
        raise RuntimeError("no_usable_source_records")
    report = {
        "schema_version": "tts-voice-corpus-audit-v1",
        "source_dataset": SOURCE_DATASET,
        "source_revision": SOURCE_REVISION,
        "quality_policy": "matches_v4_basic_acoustic_and_text_length_filters",
        "known_first_music_excluded": True,
        "contains_audio_or_transcripts": False,
        "counts": dict(counts),
        "rejection_reasons_nonexclusive": dict(rejected),
        "duration_counts_seconds": dict(durations),
        "text_character_count_bins": dict(text_lengths),
        "valid_audio_seconds": round(seconds_all, 2),
        "quality_accepted_seconds": round(seconds_accepted, 2),
        "reference_eligible_seconds": round(seconds_reference, 2),
        "limitations": ["acoustic screening does not verify transcript alignment", "does not detect all music, noise or speaker changes", "exact duplicates only; near duplicates are not measured"],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "run_metadata.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
