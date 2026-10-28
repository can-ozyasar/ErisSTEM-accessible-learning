"""Private paired V3/T3 evaluation for the grouped V5 quality model."""

from __future__ import annotations

import gc
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

SOURCE = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-history-tts-finetune-eval-v1")
OUTPUT = Path("/kaggle/working/eristem-tts-v5-new-history-eval")
TRAINED_OUTPUT_DIR = "eristem-private-chatterbox-v3-finetune-v5"

MODEL_REPOSITORY = "ResembleAI/chatterbox"
MODEL_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
CHATTERBOX_COMMIT = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
VOICE_REPOSITORY = "omersaidd/tts_nisan_kumru_tur"
VOICE_REVISION = "678712b026da89058feb010886de23983cc8563b"
MODEL_FILES = ("ve.pt", "t3_mtl23ls_v3.safetensors", "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json")
SEED = 20261020


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


# A private notebook package injects the reviewed source-bound items here.
EXPERIMENT_GOLD = None


def gold_items() -> tuple[Path, list[dict]]:
    previous = list(SOURCE.rglob("tts-history-eval-v1.json"))
    if len(previous) != 1 or not isinstance(EXPERIMENT_GOLD, dict):
        raise RuntimeError("missing_previous_or_new_gold")
    old = json.loads(previous[0].read_text(encoding="utf-8"))
    items = EXPERIMENT_GOLD.get("items")
    if EXPERIMENT_GOLD.get("schema_version") != "tts-history-eval-v1" or not isinstance(items, list) or len(items) != 8:
        raise RuntimeError("invalid_new_gold")
    old_text = {x["expected_spoken_text"] for x in old["items"]}
    if len({x["id"] for x in items}) != 8 or any(x["expected_spoken_text"] in old_text or not x["expected_spoken_text"].strip() for x in items):
        raise RuntimeError("new_gold_duplicates_or_invalid")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "private-new-history-gold.json"
    path.write_text(json.dumps(EXPERIMENT_GOLD, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, items


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


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        raise RuntimeError("Bu değerlendirme yalnız private Kaggle notebook içinde çalışır")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    install_runtime()
    import numpy as np
    import soundfile as sf
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    from huggingface_hub import snapshot_download

    if not torch.cuda.is_available():
        raise RuntimeError("V3 ses üretimi için Kaggle GPU gerekli")
    manifest, items = gold_items()
    tuned = trained_weight()
    reference, reference_position = reference_waveform()
    reference_path = OUTPUT / "private-reference.wav"
    sf.write(reference_path, reference, 24_000)
    checkpoint = Path(snapshot_download(repo_id=MODEL_REPOSITORY, revision=MODEL_REVISION, allow_patterns=list(MODEL_FILES)))
    if any(not (checkpoint / name).is_file() for name in MODEL_FILES):
        raise RuntimeError("Sabit V3 temel ağırlıkları eksik")
    tuned_checkpoint = OUTPUT / "tuned-checkpoint"
    tuned_checkpoint.mkdir(exist_ok=True)
    for name in MODEL_FILES:
        (tuned_checkpoint / name).symlink_to(tuned if name == "t3_mtl23ls_v3.safetensors" else checkpoint / name)
    audio_dir = OUTPUT / "paired-audio"
    audio_dir.mkdir(exist_ok=True)
    records = []
    for candidate, weights in (("base", checkpoint), ("grouped_v5", tuned_checkpoint)):
        model = ChatterboxMultilingualTTS.from_local(str(weights), device="cuda", t3_model="v3")
        for index, item in enumerate(items):
            item_id = item["id"]
            audio_path = audio_dir / f"{candidate}.{item_id}.wav"
            random.seed(SEED + index)
            np.random.seed(SEED + index)
            torch.manual_seed(SEED + index)
            torch.cuda.manual_seed_all(SEED + index)
            started = time.monotonic()
            try:
                waveform = model.generate(item["expected_spoken_text"], language_id="tr", audio_prompt_path=str(reference_path))
                samples = waveform.detach().float().cpu().numpy().squeeze()
                duration = len(samples) / model.sr if samples.ndim == 1 else 0.0
                if samples.ndim != 1 or not np.isfinite(samples).all() or not 0 < duration < 120:
                    raise RuntimeError("Geçersiz veya aşırı uzun ses çıktısı")
                samples = samples * 0.60
                if float(np.max(np.abs(samples))) >= 0.999:
                    raise RuntimeError("Sabit kazançtan sonra genlik sınırı aşıldı")
                sf.write(audio_path, samples, model.sr)
                records.append({"id": item_id, "candidate": candidate, "status": "generated", "audio_path": f"paired-audio/{audio_path.name}", "audio_sha256": sha256(audio_path), "duration_seconds": round(duration, 3), "generation_seconds": round(time.monotonic() - started, 3), "peak": round(float(np.max(np.abs(samples))), 4)})
            except (RuntimeError, OSError, ValueError, TypeError) as error:
                records.append({"id": item_id, "candidate": candidate, "status": "failed", "error_type": type(error).__name__})
            (OUTPUT / "run_records.json").write_text(json.dumps({"schema_version": "tts-v3-finetune-new-history-v1", "input_sha256": sha256(manifest), "items_total": len(items) * 2, "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
        del model
        gc.collect()
        torch.cuda.empty_cache()
    (OUTPUT / "run_metadata.json").write_text(json.dumps({"schema_version": "tts-v3-finetune-new-history-meta-v1", "candidate": "base-v3-vs-t3-grouped-v5", "input_sha256": sha256(manifest), "base_revision": MODEL_REVISION, "trained_sha256": sha256(tuned), "code_commit": CHATTERBOX_COMMIT, "voice_revision": VOICE_REVISION, "reference_position": reference_position, "reference_sha256": sha256(reference_path), "seed": SEED, "device": torch.cuda.get_device_name(0), "samples_generated": sum(row["status"] == "generated" for row in records), "samples_failed": sum(row["status"] == "failed" for row in records), "student_publication": "blocked_pending_asr_and_blind_listening"}, ensure_ascii=False, indent=2), encoding="utf-8")
    if any(row["status"] != "generated" for row in records):
        raise RuntimeError("En az bir tarih sesi üretilemedi")


if __name__ == "__main__":
    main()
