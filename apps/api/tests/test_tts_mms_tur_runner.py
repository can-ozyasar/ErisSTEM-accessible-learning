import importlib.util
import json
from pathlib import Path

import pytest


def runner_module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "tts_mms_tur_runner.py"
    spec = importlib.util.spec_from_file_location("tts_mms_tur_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_mms_runner_accepts_bounded_sealed_gold_manifest(tmp_path: Path):
    module = runner_module()
    manifest = tmp_path / "tts-gold-v1.json"
    manifest.write_text(
        json.dumps({
            "schema_version": "tts-gold-v1",
            "items": [{"id": "formula-01", "kind": "formula", "expected_spoken_text": "private text"}],
        }),
        encoding="utf-8",
    )

    assert module.load_gold(manifest) == [{"id": "formula-01", "kind": "formula", "text": "private text"}]


def test_mms_runner_rejects_path_like_gold_item_id(tmp_path: Path):
    module = runner_module()
    manifest = tmp_path / "tts-gold-v1.json"
    manifest.write_text(
        json.dumps({
            "schema_version": "tts-gold-v1",
            "items": [{"id": "../outside", "kind": "text", "expected_spoken_text": "private text"}],
        }),
        encoding="utf-8",
    )

    with pytest.raises(module.TtsInputError, match="invalid_tts_gold_item"):
        module.load_gold(manifest)


def test_mms_runner_uses_a_stable_per_item_seed_and_vits_capable_runtime(monkeypatch):
    module = runner_module()
    assert module.item_seed("formula-01") == module.item_seed("formula-01")
    assert module.item_seed("formula-01") != module.item_seed("formula-02")
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda command, check: calls.append((command, check)))

    module.install_mms_runtime()

    command, check = calls[0]
    assert check is True
    assert "transformers>=4.33,<5" in command
    assert "accelerate" in command
