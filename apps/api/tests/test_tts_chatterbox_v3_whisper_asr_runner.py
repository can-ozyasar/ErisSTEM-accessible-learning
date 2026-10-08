import hashlib
import importlib.util
import json
from pathlib import Path


def runner_module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "tts_chatterbox_v3_whisper_asr_runner.py"
    spec = importlib.util.spec_from_file_location("tts_chatterbox_v3_whisper_asr_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_v3_asr_runner_accepts_only_checksum_verified_private_wavs(tmp_path: Path):
    module = runner_module()
    audio = tmp_path / "audio" / "formula-01.wav"
    audio.parent.mkdir()
    payload = b"private synthesized wav"
    audio.write_bytes(payload)
    manifest = tmp_path / "tts-asr-input.json"
    manifest.write_text(json.dumps({
        "schema_version": "tts-asr-input-v1", "candidate": "v3-a", "assets": [{
            "id": "formula-01", "kind": "formula", "audio_path": "audio/formula-01.wav",
            "audio_sha256": hashlib.sha256(payload).hexdigest(),
        }],
    }), encoding="utf-8")

    candidate, assets = module.load_assets(manifest)

    assert candidate == "v3-a"
    assert assets[0]["audio_path"] == audio
    assert "eristem-meb9-tts-chatterbox-v3-audio-v1" in str(module.INPUT)
