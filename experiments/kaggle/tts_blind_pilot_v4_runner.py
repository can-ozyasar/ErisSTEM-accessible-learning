"""Prepare a private, balanced listening study on Kaggle without local downloads."""

from __future__ import annotations

import gc
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-history-tts-finetune-eval-v1")
OUTPUT = Path("/kaggle/working/eristem-private-blind-pilot-v4")
MODEL_FILES = ("ve.pt", "t3_mtl23ls_v3.safetensors", "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json")
BASE_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
CODE_COMMIT = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
VOICE_REVISION = "678712b026da89058feb010886de23983cc8563b"
WEIGHTS = {
    "pilot": ("eristem-private-chatterbox-v3-finetune-v3", "c1838de5473a99ed51a811b44c4fd3311dfc0427233a5deb2fcf6e6ecde7b111"),
    "v4": ("eristem-private-chatterbox-v3-finetune-v4", "274bfe98e45280aab2687f456bb94a86d0adfa3c220b9f0137a7c32f22648493"),
}
SEED = 20261020
GAIN = 0.60


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        raise RuntimeError("private_kaggle_only")
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "--yes", "torchvision", "peft"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "datasets==3.6.0", "transformers==4.52.4", "accelerate==1.7.0", "soundfile>=0.12", "librosa>=0.10", "safetensors"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", f"git+https://github.com/resemble-ai/chatterbox.git@{CODE_COMMIT}"], check=True)
    import librosa
    import numpy as np
    import soundfile as sf
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    from datasets import load_dataset
    from huggingface_hub import snapshot_download

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_required")
    gold_files = list(SOURCE.rglob("tts-history-eval-v1.json"))
    if len(gold_files) != 1:
        raise RuntimeError("missing_gold")
    gold = json.loads(gold_files[0].read_text(encoding="utf-8"))
    items = gold.get("items", [])
    if gold.get("schema_version") != "tts-history-eval-v1" or len(items) != 14 or len({item["id"] for item in items}) != 14:
        raise RuntimeError("invalid_gold")

    weight_paths = {}
    for candidate, (directory, digest) in WEIGHTS.items():
        matches = [p for p in Path("/kaggle/input").rglob("t3_mtl23ls_v3.safetensors") if p.parent.name == directory]
        if len(matches) != 1 or sha256(matches[0]) != digest:
            raise RuntimeError("weight_checksum_mismatch")
        weight_paths[candidate] = matches[0]

    # Repeat the previous study's reference selection exactly, including the
    # known music exclusion. The source remains private in Kaggle.
    reference = None
    for position, row in enumerate(load_dataset("omersaidd/tts_nisan_kumru_tur", split="train", streaming=True, revision=VOICE_REVISION), start=1):
        if position > 128:
            break
        if position == 1:
            continue
        audio = row.get("audio")
        if not isinstance(audio, dict) or not isinstance(audio.get("sampling_rate"), int):
            continue
        samples = np.asarray(audio.get("array"), dtype=np.float32)
        if samples.ndim == 2:
            samples = samples.mean(axis=1)
        rate = audio["sampling_rate"]
        if samples.ndim != 1 or rate <= 0 or not 8 <= len(samples) / rate <= 12:
            continue
        peak = float(np.max(np.abs(samples)))
        rms = float(np.sqrt(np.mean(samples * samples)))
        if not 0.005 <= rms <= 0.5 or peak <= 0.02 or float(np.mean(np.abs(samples) >= 0.999)) > 0.002:
            continue
        reference = librosa.resample(samples, orig_sr=rate, target_sr=24_000) if rate != 24_000 else samples
        break
    if reference is None:
        raise RuntimeError("missing_reference")

    checkpoint = Path(snapshot_download(repo_id="ResembleAI/chatterbox", revision=BASE_REVISION, allow_patterns=list(MODEL_FILES)))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    indices = list(range(len(items)))
    random.Random(SEED + 891).shuffle(indices)
    pilot_a = set(indices[: len(indices) // 2])
    assignments = {str(i + 1): {"A": "pilot" if i in pilot_a else "v4", "B": "v4" if i in pilot_a else "pilot"} for i in range(len(items))}
    records = []
    with tempfile.TemporaryDirectory(prefix="eristem-blind-") as temp:
        root = Path(temp)
        ref_path = root / "reference.wav"
        sf.write(ref_path, reference, 24_000, subtype="PCM_16")
        for candidate in ("pilot", "v4"):
            model_dir = root / candidate
            model_dir.mkdir()
            for name in MODEL_FILES:
                (model_dir / name).symlink_to(weight_paths[candidate] if name == "t3_mtl23ls_v3.safetensors" else checkpoint / name)
            model = ChatterboxMultilingualTTS.from_local(str(model_dir), device="cuda", t3_model="v3")
            for index, item in enumerate(items):
                random.seed(SEED + index)
                np.random.seed(SEED + index)
                torch.manual_seed(SEED + index)
                torch.cuda.manual_seed_all(SEED + index)
                waveform = model.generate(item["expected_spoken_text"], language_id="tr", audio_prompt_path=str(ref_path))
                samples = waveform.detach().float().cpu().numpy().squeeze()
                if samples.ndim != 1 or not np.isfinite(samples).all() or not 1 <= len(samples) / model.sr <= 20:
                    raise RuntimeError("invalid_generated_audio")
                samples = samples * GAIN
                if float(np.max(np.abs(samples))) >= 0.999:
                    raise RuntimeError("fixed_gain_insufficient")
                label = next(label for label, name in assignments[str(index + 1)].items() if name == candidate)
                path = OUTPUT / f"{index + 1:02d}-{label}.wav"
                sf.write(path, samples, model.sr, subtype="PCM_16")
                records.append({"number": index + 1, "label": label, "sha256": sha256(path), "seconds": round(len(samples) / model.sr, 3), "peak": round(float(np.max(np.abs(samples))), 5)})
            del model
            gc.collect()
            torch.cuda.empty_cache()
    (OUTPUT / "blind-report.json").write_text(json.dumps({"schema_version": "tts-blind-pilot-v4-v1", "input_sha256": sha256(gold_files[0]), "fixed_gain": GAIN, "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    # This separate key is used only after the listener submits their choices.
    (Path("/kaggle/working") / "private-blind-answer-key.json").write_text(json.dumps({"assignments": assignments}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("14 kör A/B çifti hazır. Lütfen cevap anahtarını açmadan dinleyin.")


if __name__ == "__main__":
    main()
