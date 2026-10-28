"""Produce private, unreviewed source-bound V5 demonstration audio."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-tts-v5-demo-input-v1")
OUTPUT = Path("/kaggle/working/eristem-tts-v5-demo-generated-v1")
TRAINED_OUTPUT_DIR = "eristem-private-chatterbox-v3-finetune-v5"

MODEL_REPOSITORY = "ResembleAI/chatterbox"
MODEL_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
CHATTERBOX_COMMIT = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
VOICE_REPOSITORY = "omersaidd/tts_nisan_kumru_tur"
VOICE_REVISION = "678712b026da89058feb010886de23983cc8563b"
MODEL_FILES = ("ve.pt", "t3_mtl23ls_v3.safetensors", "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json")
SEED = 20261020
MAX_UNIQUE = int(os.getenv("ERISTEM_V5_DEMO_MAX_UNIQUE", "0"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def install_runtime() -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "pip"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "--yes", "torchvision", "peft"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "datasets==3.6.0", "transformers==4.52.4", "accelerate==1.7.0", "soundfile>=0.12", "librosa>=0.10", "safetensors"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", f"git+https://github.com/resemble-ai/chatterbox.git@{CHATTERBOX_COMMIT}"], check=True)


def trained_weight() -> Path:
    paths = [path for path in Path("/kaggle/input").rglob("t3_mtl23ls_v3.safetensors") if path.parent.name == TRAINED_OUTPUT_DIR]
    if len(paths) != 1:
        raise RuntimeError("Eğitilmiş V5 T3 ağırlığı tek olarak bulunamadı")
    manifests = list(paths[0].parent.glob("artifact_manifest.json"))
    metadata = list(paths[0].parent.glob("run_metadata.json"))
    if len(manifests) != 1 or len(metadata) != 1:
        raise RuntimeError("V5 eğitim raporları eksik")
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    run = json.loads(metadata[0].read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    if (run.get("candidate") != "chatterbox-multilingual-v3-t3-cross-reference-v5-grouped-quality"
            or len(files) != 1 or files[0].get("path") != paths[0].name
            or files[0].get("bytes") != paths[0].stat().st_size
            or files[0].get("sha256") != sha256(paths[0])):
        raise RuntimeError("V5 eğitim kaynağı veya ağırlık doğrulaması başarısız")
    return paths[0]


def reference_waveform():
    import librosa
    import numpy as np
    from datasets import load_dataset

    source = load_dataset(VOICE_REPOSITORY, split="train", streaming=True, revision=VOICE_REVISION)
    for position, row in enumerate(source, start=1):
        if position > 128:
            break
        if position == 1:
            continue
        audio = row.get("audio") if isinstance(row, dict) else None
        if not isinstance(audio, dict) or not isinstance(audio.get("sampling_rate"), int):
            continue
        samples = np.asarray(audio.get("array"), dtype=np.float32)
        if samples.ndim == 2:
            samples = samples.mean(axis=1)
        rate = audio["sampling_rate"]
        if samples.ndim != 1 or rate <= 0 or not 8 <= len(samples) / rate <= 12:
            continue
        peak, rms = float(np.max(np.abs(samples))), float(np.sqrt(np.mean(samples * samples)))
        clipping = float(np.mean(np.abs(samples) >= 0.999))
        if not 0.005 <= rms <= 0.5 or peak <= 0.02 or clipping > 0.002:
            continue
        if rate != 24_000:
            samples = librosa.resample(samples, orig_sr=rate, target_sr=24_000)
        return samples, position
    raise RuntimeError("İzinli kaynakta teknik olarak uygun referans bulunamadı")


def chunks(text: str, limit: int = 220) -> list[str]:
    parts = []
    current = ""
    for word in text.split():
        if len(word) > limit:
            raise ValueError("word_too_long")
        candidate = f"{current} {word}" if current else word
        if len(candidate) > limit:
            parts.append(current)
            current = word
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        raise RuntimeError("private_kaggle_only")
    install_runtime()
    import numpy as np
    import soundfile as sf
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    from huggingface_hub import snapshot_download

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_required")
    manifests = list(SOURCE.rglob("manifest.json"))
    if len(manifests) != 1:
        raise RuntimeError("missing_manifest")
    payload = json.loads(manifests[0].read_text(encoding="utf-8"))
    items = payload.get("items")
    if payload.get("schema_version") != "v5-demo-input-v1" or not isinstance(items, list) or not items:
        raise RuntimeError("invalid_manifest")
    seen = {}
    skipped = 0
    for item in items:
        text, digest = item.get("spoken_text"), item.get("spoken_text_sha256")
        if not isinstance(text, str) or not text.strip() or hashlib.sha256(text.encode()).hexdigest() != digest:
            raise RuntimeError("text_checksum_mismatch")
        contains_digits = bool(re.search(r"\d", text))
        if item.get("contains_digits") is not contains_digits:
            raise RuntimeError("numeric_review_flag_mismatch")
        if contains_digits:
            skipped += 1
            continue
        if digest in seen and seen[digest] != text:
            raise RuntimeError("digest_collision")
        seen[digest] = text
    tuned = trained_weight()
    tuned_sha = sha256(tuned)
    reference, _ = reference_waveform()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    audio_dir = OUTPUT / "audio"
    audio_dir.mkdir(exist_ok=True)
    temporary_dir = Path(tempfile.mkdtemp(prefix="eristem-v5-demo-", dir="/tmp"))
    reference_path = temporary_dir / "temporary-reference.wav"
    sf.write(reference_path, reference, 24_000, subtype="PCM_16")
    checkpoint = Path(snapshot_download(repo_id=MODEL_REPOSITORY, revision=MODEL_REVISION, allow_patterns=list(MODEL_FILES)))
    model_dir = temporary_dir / "temporary-checkpoint"
    model_dir.mkdir(exist_ok=True)
    for name in MODEL_FILES:
        (model_dir / name).symlink_to(tuned if name == "t3_mtl23ls_v3.safetensors" else checkpoint / name)
    model = ChatterboxMultilingualTTS.from_local(str(model_dir), device="cuda", t3_model="v3")
    records = []
    selected = sorted(seen.items())[:MAX_UNIQUE] if MAX_UNIQUE > 0 else sorted(seen.items())
    for position, (digest, text) in enumerate(selected, 1):
        try:
            waves = []
            for part_no, part in enumerate(chunks(text)):
                random.seed(SEED + position * 100 + part_no)
                np.random.seed(SEED + position * 100 + part_no)
                torch.manual_seed(SEED + position * 100 + part_no)
                torch.cuda.manual_seed_all(SEED + position * 100 + part_no)
                with torch.inference_mode():
                    wave = model.generate(part, language_id="tr", audio_prompt_path=str(reference_path))
                samples = wave.detach().float().cpu().numpy().squeeze() * 0.60
                duration = len(samples) / model.sr if samples.ndim == 1 else 0
                if not np.isfinite(samples).all() or not 0.25 <= duration <= 40 or float(np.max(np.abs(samples))) >= 0.999:
                    raise ValueError("invalid_audio")
                if waves:
                    waves.append(np.zeros(int(model.sr * 0.12), dtype=np.float32))
                waves.append(samples)
            samples = np.concatenate(waves)
            target = audio_dir / f"{digest}.wav"
            sf.write(target, samples, model.sr, subtype="PCM_16")
            records.append({"spoken_text_sha256": digest, "status": "generated", "audio_sha256": sha256(target), "bytes": target.stat().st_size, "duration_seconds": round(len(samples) / model.sr, 3)})
        except (RuntimeError, OSError, ValueError, TypeError) as error:
            records.append({"spoken_text_sha256": digest, "status": "failed", "error_type": type(error).__name__})
        (OUTPUT / "run_records.json").write_text(json.dumps({"schema_version":"v5-demo-audio-v1", "input_sha256":sha256(manifests[0]), "model_sha256":tuned_sha, "pilot_limit": MAX_UNIQUE, "requires_listening_review":True, "records":records}, indent=2), encoding="utf-8")
        if position % 20 == 0:
            print(f"Processed {position}/{len(selected)} unique texts", flush=True)
    shutil.rmtree(temporary_dir)
    print(json.dumps({"unique_generated":sum(r["status"] == "generated" for r in records), "unique_failed":sum(r["status"] == "failed" for r in records), "entries_skipped_for_numeric_review":skipped, "pilot_limit": MAX_UNIQUE}, ensure_ascii=False))
    if any(r["status"] != "generated" for r in records):
        raise RuntimeError("some_units_failed")


if __name__ == "__main__":
    main()
