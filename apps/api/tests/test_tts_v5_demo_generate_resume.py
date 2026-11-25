import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def runner_module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "tts_v5_demo_generate.py"
    spec = importlib.util.spec_from_file_location("tts_v5_demo_generate", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def wav_bytes():
    return b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 32


def run_metadata(module):
    runtime = {"gpu_name": "test-gpu"}
    return {
        "schema_version": module.RUN_SCHEMA,
        "input_sha256": "1" * 64,
        "model_sha256": "2" * 64,
        "pilot_limit": 0,
        "runner_sha256": "3" * 64,
        "model_repository": "base-model",
        "model_revision": "base-revision",
        "chatterbox_commit": "source-commit",
        "voice_repository": "voice-reference",
        "voice_revision": "voice-revision",
        "seed": 42,
        "reference_sha256": "4" * 64,
        "reference_dataset_row": 2,
        "sample_rate": 24_000,
        "runtime_sha256": hashlib.sha256(json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "runtime": runtime,
        "records": [],
    }


def test_v5_run_checkpoint_is_atomic_and_exact_generated_audio_can_resume(tmp_path: Path):
    module = runner_module()
    output = tmp_path / "run"
    digest = "a" * 64
    wav = wav_bytes()
    audio = output / "audio" / f"{digest}.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(wav)
    row = {"spoken_text_sha256": digest, "status": "generated", "audio_sha256": hashlib.sha256(wav).hexdigest(),
           "bytes": len(wav), "duration_seconds": 1.0}
    run = {**run_metadata(module), "started_at_utc": "2026-01-01T00:00:00+00:00", "records": [row]}

    module.persist_run_records(output, run)
    resumed, started_at = module.load_resumable_records(output, run, {digest})

    assert resumed == {digest: row}
    assert started_at == run["started_at_utc"]
    assert json.loads((output / "run_records.json").read_text(encoding="utf-8")) == run
    assert not (output / ".run_records.json.tmp").exists()


def test_v5_resume_rejects_different_input_or_generation_configuration(tmp_path: Path):
    module = runner_module()
    output = tmp_path / "run"
    run = {**run_metadata(module), "started_at_utc": "2026-01-01T00:00:00+00:00", "records": []}
    module.persist_run_records(output, run)
    changed = {**run, "model_sha256": "f" * 64}

    with pytest.raises(RuntimeError, match="resume_manifest_binding_mismatch"):
        module.load_resumable_records(output, changed, set())


def test_v5_resume_rejects_tampered_environment_metadata(tmp_path: Path):
    module = runner_module()
    output = tmp_path / "run"
    run = {**run_metadata(module), "started_at_utc": "2026-01-01T00:00:00+00:00", "records": []}
    module.persist_run_records(output, run)
    tampered = {**run, "runtime": {"gpu_name": "different-gpu"}}
    module.persist_run_records(output, tampered)

    with pytest.raises(RuntimeError, match="resume_manifest_runtime_checksum_mismatch"):
        module.load_resumable_records(output, run, set())


def test_v5_resume_retries_missing_or_corrupt_audio_and_rejects_unknown_units(tmp_path: Path):
    module = runner_module()
    output = tmp_path / "run"
    digest = "b" * 64
    run = {**run_metadata(module), "started_at_utc": "2026-01-01T00:00:00+00:00",
           "records": [{"spoken_text_sha256": digest, "status": "generated",
                        "audio_sha256": "c" * 64, "bytes": 44}]}
    module.persist_run_records(output, run)
    resumed, _ = module.load_resumable_records(output, run, {digest})
    assert resumed == {}

    run["records"] = [{"spoken_text_sha256": "d" * 64, "status": "failed"}]
    module.persist_run_records(output, run)
    with pytest.raises(RuntimeError, match="resume_manifest_unit_mismatch"):
        module.load_resumable_records(output, run, {digest})
