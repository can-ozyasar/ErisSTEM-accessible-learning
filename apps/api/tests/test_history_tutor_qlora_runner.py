import importlib.util
import json
from pathlib import Path

import pytest


def runner_module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "history_tutor_qwen14b_qlora.py"
    spec = importlib.util.spec_from_file_location("history_tutor_qlora_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_resume_requires_hash_bound_complete_trainer_checkpoint(tmp_path, monkeypatch):
    module = runner_module()
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text('{"schema":"input"}', encoding="utf-8")
    checkpoint = tmp_path / "checkpoint-12"
    checkpoint.mkdir()
    for name in ("trainer_state.json", "optimizer.pt", "scheduler.pt", "adapter_config.json", "adapter_model.safetensors"):
        (checkpoint / name).write_text(name, encoding="utf-8")
    contract = {"epochs": 3, "seed": 42}
    monkeypatch.setattr(module, "CHECKPOINT_MANIFEST", tmp_path / "resume_checkpoint_manifest.json")
    module.write_checkpoint_manifest(checkpoint, source, contract)
    monkeypatch.setenv("TUTOR_QLORA_RESUME_CHECKPOINT", str(checkpoint))

    assert module.verified_resume_checkpoint(source, contract) == checkpoint.resolve()

    (checkpoint / "optimizer.pt").write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        module.verified_resume_checkpoint(source, contract)


def test_input_manifest_rejects_a_two_epoch_dataset_before_gpu_initialization(tmp_path):
    module = runner_module()
    for name in ("train.jsonl", "dev.jsonl"):
        (tmp_path / name).write_text('{"group_id":"q"}\n', encoding="utf-8")
    manifest = {
        "schema": "eristem-tutor-qlora-experiment-input-v1", "base_model": module.MODEL,
        "base_model_revision": module.REVISION, "answer_keys_included": False,
        "sealed_test_uploaded": False, "student_data_included": False,
        "training_contract": {"epochs": 2},
        "files": {name: module.sha256(tmp_path / name) for name in ("train.jsonl", "dev.jsonl")},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="3-epoch"):
        module.input_manifest(tmp_path)


def test_mount_resolution_deduplicates_default_and_legacy_slug_paths(tmp_path, monkeypatch):
    module = runner_module()
    mounted = tmp_path / "history-tutor-qlora-input-resume-v4"
    mounted.mkdir()
    for name in ("manifest.json", "train.jsonl", "dev.jsonl"):
        (mounted / name).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "KAGGLE_DATASET_HANDLE", "owner/history-tutor-qlora-input-resume-v4")
    legacy = module.Path("/kaggle/input/history-tutor-qlora-input-resume-v4")
    monkeypatch.setattr(module, "INPUT", legacy)

    assert module.allowed_input_paths().count(legacy) == 1
    assert len(module.allowed_input_paths()) == 2
