import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "experiments/kaggle/install_v5_demo_audio.py"
spec = importlib.util.spec_from_file_location("install_v5_audio", SCRIPT)
installer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(installer)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path):
    text = "Sonraki soru."
    text_hash = _digest(text.encode())
    source = {"schema_version": "ayt-history-v5-static-audio-input-v1", "pack_checksum": "a" * 64,
              "voice_model_sha256": installer.MODEL_SHA,
              "items": [{"kind": "interface", "id": "interface:" + text_hash, "spoken_text": text,
                         "spoken_text_sha256": text_hash}]}
    source_path = tmp_path / "manifest.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    generated = tmp_path / "generated"
    (generated / "audio").mkdir(parents=True)
    wav = b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32
    (generated / "audio" / f"{text_hash}.wav").write_bytes(wav)
    records = {"schema_version": "v5-demo-audio-v1", "input_sha256": _digest(source_path.read_bytes()),
               "model_sha256": installer.MODEL_SHA, "pilot_limit": 0,
               "records": [{"spoken_text_sha256": text_hash, "status": "generated", "bytes": len(wav), "audio_sha256": _digest(wav)}]}
    (generated / "run_records.json").write_text(json.dumps(records))
    return source_path, generated, text_hash


def test_installs_exam_manifest_with_pack_binding_and_interface_identity(tmp_path):
    source, generated, text_hash = _fixture(tmp_path)
    destination = tmp_path / "installed"
    assert installer.install(source, generated, destination) == 1
    index = json.loads((destination / "index.json").read_text())
    assert index["source_sha256"]["question"] == "a" * 64
    assert index["items"][0]["id"] == text_hash
    assert index["runtime_enabled"] is False
    assert index["requires_listening_review"] is True


def test_rejects_missing_exam_audio(tmp_path):
    source, generated, _ = _fixture(tmp_path)
    records = json.loads((generated / "run_records.json").read_text())
    records["records"] = []
    (generated / "run_records.json").write_text(json.dumps(records))
    with pytest.raises(ValueError, match="missing_required_generated_audio"):
        installer.install(source, generated, tmp_path / "installed")


def test_rejects_source_manifest_bound_to_different_voice_model(tmp_path):
    source, generated, _ = _fixture(tmp_path)
    manifest = json.loads(source.read_text())
    manifest["voice_model_sha256"] = "0" * 64
    source.write_text(json.dumps(manifest), encoding="utf-8")
    records = json.loads((generated / "run_records.json").read_text())
    records["input_sha256"] = _digest(source.read_bytes())
    (generated / "run_records.json").write_text(json.dumps(records), encoding="utf-8")

    with pytest.raises(ValueError, match="source_voice_model_mismatch"):
        installer.install(source, generated, tmp_path / "installed")
