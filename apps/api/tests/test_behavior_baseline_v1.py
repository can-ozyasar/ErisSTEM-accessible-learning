"""Regression tests for the paired QLoRA behavior screen runner."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


def behavior_module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "behavior_baseline_v1.py"
    spec = importlib.util.spec_from_file_location("behavior_baseline_v1", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_adapter_input_accepts_verified_adapter_at_configured_mount(tmp_path, monkeypatch):
    module = behavior_module()
    files = {"adapter_config.json": b"config", "adapter_model.safetensors": b"weights"}
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)
    monkeypatch.setattr(module, "ADAPTER_INPUT", tmp_path)
    monkeypatch.setattr(
        module,
        "ADAPTER_FILE_SHA256",
        {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    )

    assert module.resolve_adapter_input() == tmp_path


def test_resolve_adapter_input_rejects_checksum_mismatch(tmp_path, monkeypatch):
    module = behavior_module()
    for name in module.ADAPTER_FILE_SHA256:
        (tmp_path / name).write_bytes(b"untrusted")
    monkeypatch.setattr(module, "ADAPTER_INPUT", tmp_path)

    with pytest.raises(RuntimeError, match="checksum uyuşmazlığı"):
        module.resolve_adapter_input()
