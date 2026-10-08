import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def runner_module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "tts_whisper_asr_runner.py"
    spec = importlib.util.spec_from_file_location("tts_whisper_asr_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_asr_runner_loads_only_checksum_verified_private_wavs(tmp_path: Path):
    module = runner_module()
    audio = tmp_path / "audio" / "formula-01.wav"
    audio.parent.mkdir()
    audio_bytes = b"private synthesized wav"
    audio.write_bytes(audio_bytes)
    manifest = tmp_path / "tts-asr-input.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "tts-asr-input-v1",
                "candidate": "voice-a",
                "assets": [
                    {
                        "id": "formula-01",
                        "kind": "formula",
                        "audio_path": "audio/formula-01.wav",
                        "audio_sha256": hashlib.sha256(audio_bytes).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    candidate, assets = module.load_assets(manifest)

    assert candidate == "voice-a"
    assert assets == [
        {
            "id": "formula-01",
            "kind": "formula",
            "audio_path": audio,
            "audio_sha256": hashlib.sha256(audio_bytes).hexdigest(),
        }
    ]


def test_asr_runner_rejects_wav_path_outside_the_private_input_package(tmp_path: Path):
    module = runner_module()
    manifest = tmp_path / "tts-asr-input.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "tts-asr-input-v1",
                "candidate": "voice-a",
                "assets": [
                    {
                        "id": "formula-01",
                        "kind": "formula",
                        "audio_path": "../outside.wav",
                        "audio_sha256": "a" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(module.AsrInputError, match="tts_asr_audio_integrity_mismatch"):
        module.load_assets(manifest)


def test_asr_runner_refreshes_pyav_for_the_current_faster_whisper_decoder(monkeypatch):
    module = runner_module()
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda command, check: calls.append((command, check)))

    module.install_asr_runtime()

    command, check = calls[0]
    assert check is True
    assert "faster-whisper==1.2.1" in command
    assert "av>=14,<17" in command
    assert "--force-reinstall" in command
