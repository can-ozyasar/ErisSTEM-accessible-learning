"""Produce private, unreviewed source-bound V5 demonstration audio."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

# The default retains the reproducible book-demo run.  A published AYT pack
# supplies its own private dataset path at submission time; no question text
# is embedded in this notebook.
SOURCE = Path(os.getenv("ERISTEM_V5_INPUT_PATH", "/kaggle/input"))
OUTPUT = Path(os.getenv("ERISTEM_V5_OUTPUT_PATH", "/kaggle/working/eristem-tts-v5-demo-generated-v1"))
TRAINED_OUTPUT_DIR = "eristem-private-chatterbox-v3-finetune-v5"
EXPECTED_MODEL_SHA256 = "8ec3a3312b9586a8650c38d2c8e8e8b6214851f13afbaa935ed4c9d598af8503"

MODEL_REPOSITORY = "ResembleAI/chatterbox"
MODEL_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
CHATTERBOX_COMMIT = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
VOICE_REPOSITORY = "omersaidd/tts_nisan_kumru_tur"
VOICE_REVISION = "678712b026da89058feb010886de23983cc8563b"
MODEL_FILES = ("ve.pt", "t3_mtl23ls_v3.safetensors", "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json")
SEED = 20261020
MAX_UNIQUE = int(os.getenv("ERISTEM_V5_DEMO_MAX_UNIQUE", "0"))
RUN_SCHEMA = "v5-demo-audio-v1"
RUN_BINDING_KEYS = (
    "input_sha256", "model_sha256", "pilot_limit", "runner_sha256",
    "model_repository", "model_revision", "chatterbox_commit",
    "voice_repository", "voice_revision", "seed", "reference_sha256",
    "reference_dataset_row", "sample_rate", "runtime_sha256",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_wav(path: Path) -> bool:
    try:
        with path.open("rb") as source:
            header = source.read(12)
        return len(header) == 12 and header[:4] == b"RIFF" and header[8:] == b"WAVE"
    except OSError:
        return False


def persist_run_records(output: Path, run: dict) -> None:
    """Atomically checkpoint metadata so an interrupted GPU run is resumable."""
    output.mkdir(parents=True, exist_ok=True)
    target = output / "run_records.json"
    temporary = output / ".run_records.json.tmp"
    try:
        temporary.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def load_resumable_records(output: Path, run: dict, selected_hashes: set[str]) -> tuple[dict[str, dict], str | None]:
    """Reuse only checksum-valid audio from the same exact input/model/run."""
    path = output / "run_records.json"
    if not path.exists():
        return {}, None
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("resume_manifest_invalid_start_new_output") from error
    if not isinstance(previous, dict):
        raise TypeError("resume_manifest_root_invalid_start_new_output")
    old_runtime = previous.get("runtime")
    if not isinstance(old_runtime, dict):
        raise TypeError("resume_manifest_runtime_invalid_start_new_output")
    old_runtime_sha = hashlib.sha256(
        json.dumps(old_runtime, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if old_runtime_sha != previous.get("runtime_sha256"):
        raise RuntimeError("resume_manifest_runtime_checksum_mismatch_start_new_output")
    if previous.get("schema_version") != RUN_SCHEMA or any(
        previous.get(key) != run.get(key) for key in RUN_BINDING_KEYS
    ):
        raise RuntimeError("resume_manifest_binding_mismatch_start_new_output")
    rows = previous.get("records")
    if not isinstance(rows, list):
        raise TypeError("resume_manifest_records_invalid_start_new_output")
    resumed: dict[str, dict] = {}
    seen_rows: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("resume_manifest_record_invalid_start_new_output")
        digest = row.get("spoken_text_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise TypeError("resume_manifest_digest_invalid_start_new_output")
        if digest not in selected_hashes or digest in seen_rows:
            raise RuntimeError("resume_manifest_unit_mismatch_start_new_output")
        seen_rows.add(digest)
        if row.get("status") not in {"generated", "failed"}:
            raise RuntimeError("resume_manifest_status_invalid_start_new_output")
        if row.get("status") != "generated":
            continue
        audio_path = output / "audio" / f"{digest}.wav"
        try:
            valid = (_is_wav(audio_path) and audio_path.stat().st_size == row.get("bytes")
                     and sha256(audio_path) == row.get("audio_sha256"))
        except OSError:
            valid = False
        if valid:
            resumed[digest] = row
    return resumed, previous.get("started_at_utc")


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


def load_input_manifest(source: Path) -> tuple[Path, dict, dict[str, str], int]:
    """Find and validate exactly one supported input before installing packages."""
    if not source.is_dir():
        raise RuntimeError("input_root_missing")
    manifests = []
    for path in source.rglob("manifest.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("schema_version") in {
            "v5-demo-input-v1", "ayt-history-v5-static-audio-input-v1"
        }:
            manifests.append((path, payload))
    if len(manifests) != 1:
        raise RuntimeError(f"expected_one_v5_manifest_found_{len(manifests)}")
    manifest_path, payload = manifests[0]
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise RuntimeError("invalid_manifest_items")
    if (payload.get("schema_version") == "ayt-history-v5-static-audio-input-v1"
            and payload.get("voice_model_sha256") != EXPECTED_MODEL_SHA256):
        raise RuntimeError("input_voice_model_checksum_mismatch")
    seen: dict[str, str] = {}
    skipped = 0
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("invalid_manifest_item")
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
    if not seen:
        raise RuntimeError("no_synthesis_eligible_items")
    return manifest_path, payload, seen, skipped


def main() -> None:
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        raise RuntimeError("private_kaggle_only")
    manifest_path, payload, seen, skipped = load_input_manifest(SOURCE)
    if MAX_UNIQUE < 0:
        raise ValueError("pilot_limit_must_be_nonnegative")
    install_runtime()
    import numpy as np
    import soundfile as sf
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    from huggingface_hub import snapshot_download

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_required")
    tuned = trained_weight()
    tuned_sha = sha256(tuned)
    if payload.get("schema_version") == "ayt-history-v5-static-audio-input-v1" and tuned_sha != EXPECTED_MODEL_SHA256:
        raise RuntimeError("trained_voice_model_checksum_mismatch")
    reference, reference_row = reference_waveform()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    audio_dir = OUTPUT / "audio"
    audio_dir.mkdir(exist_ok=True)
    temporary_dir = Path(tempfile.mkdtemp(prefix="eristem-v5-demo-", dir="/tmp"))
    selected = sorted(seen.items())[:MAX_UNIQUE] if MAX_UNIQUE > 0 else sorted(seen.items())
    try:
        reference_path = temporary_dir / "temporary-reference.wav"
        sf.write(reference_path, reference, 24_000, subtype="PCM_16")
        checkpoint = Path(snapshot_download(repo_id=MODEL_REPOSITORY, revision=MODEL_REVISION,
                                            allow_patterns=list(MODEL_FILES)))
        model_dir = temporary_dir / "temporary-checkpoint"
        model_dir.mkdir(exist_ok=True)
        for name in MODEL_FILES:
            (model_dir / name).symlink_to(tuned if name == "t3_mtl23ls_v3.safetensors" else checkpoint / name)
        model = ChatterboxMultilingualTTS.from_local(str(model_dir), device="cuda", t3_model="v3")
        runtime = {
            "python_version": platform.python_version(),
            "torch_version": str(torch.__version__),
            "cuda_version": str(torch.version.cuda),
            "gpu_name": torch.cuda.get_device_name(0),
            "datasets_version": importlib.metadata.version("datasets"),
            "transformers_version": importlib.metadata.version("transformers"),
            "accelerate_version": importlib.metadata.version("accelerate"),
            "soundfile_version": importlib.metadata.version("soundfile"),
            "numpy_version": importlib.metadata.version("numpy"),
            "librosa_version": importlib.metadata.version("librosa"),
            "huggingface_hub_version": importlib.metadata.version("huggingface-hub"),
            "safetensors_version": importlib.metadata.version("safetensors"),
        }
        runtime_sha = hashlib.sha256(json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        bindings = {
            "input_sha256": sha256(manifest_path), "model_sha256": tuned_sha,
            "pilot_limit": MAX_UNIQUE, "runner_sha256": sha256(Path(__file__)),
            "model_repository": MODEL_REPOSITORY, "model_revision": MODEL_REVISION,
            "chatterbox_commit": CHATTERBOX_COMMIT, "voice_repository": VOICE_REPOSITORY,
            "voice_revision": VOICE_REVISION, "seed": SEED,
            "reference_sha256": sha256(reference_path), "reference_dataset_row": reference_row,
            "sample_rate": int(model.sr), "runtime_sha256": runtime_sha,
        }
        run = {
            "schema_version": RUN_SCHEMA, **bindings, "runtime": runtime,
            "requires_listening_review": True,
            "started_at_utc": datetime.now(UTC).isoformat(), "records": [],
        }
        completed, original_started = load_resumable_records(
            OUTPUT, run, {digest for digest, _ in selected})
        if original_started:
            run["started_at_utc"] = original_started
        records_by_digest = dict(completed)
        run["records"] = [records_by_digest[key] for key, _ in selected if key in records_by_digest]
        persist_run_records(OUTPUT, run)
        newly_generated = 0
        for position, (digest, text) in enumerate(selected, 1):
            if digest in completed:
                continue
            item_started = time.monotonic()
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
                if not _is_wav(target):
                    raise ValueError("invalid_written_wav")
                record = {"spoken_text_sha256": digest, "status": "generated", "audio_sha256": sha256(target),
                          "bytes": target.stat().st_size, "duration_seconds": round(len(samples) / model.sr, 3),
                          "generation_ms": round((time.monotonic() - item_started) * 1000)}
                newly_generated += 1
            except (RuntimeError, OSError, ValueError, TypeError) as error:
                record = {"spoken_text_sha256": digest, "status": "failed", "error_type": type(error).__name__,
                          "generation_ms": round((time.monotonic() - item_started) * 1000)}
            records_by_digest[digest] = record
            run["records"] = [records_by_digest[key] for key, _ in selected if key in records_by_digest]
            run["updated_at_utc"] = datetime.now(UTC).isoformat()
            persist_run_records(OUTPUT, run)
            if position % 20 == 0:
                print(f"Processed {position}/{len(selected)} unique texts", flush=True)
        records = [records_by_digest[key] for key, _ in selected if key in records_by_digest]
        run["records"] = records
        run["finished_at_utc"] = datetime.now(UTC).isoformat()
        run["resumed_count"] = len(completed)
        run["generated_this_run_count"] = newly_generated
        persist_run_records(OUTPUT, run)
        failed = sum(row["status"] != "generated" for row in records)
        print(json.dumps({"unique_generated":len(records) - failed, "unique_failed":failed,
                          "resumed_count":len(completed), "generated_this_run_count":newly_generated,
                          "entries_skipped_for_numeric_review":skipped, "pilot_limit":MAX_UNIQUE}, ensure_ascii=False))
        if failed or len(records) != len(selected):
            raise RuntimeError("some_units_failed")
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
