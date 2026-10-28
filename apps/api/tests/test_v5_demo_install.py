import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[3] / "experiments/kaggle/install_v5_demo_audio.py"
spec = importlib.util.spec_from_file_location("install_v5_demo_audio", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_installer_binds_source_and_rejects_corrupt_audio(tmp_path):
    text = "Merhaba tarih"
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    manifest = {"schema_version": "v5-demo-input-v1", "history_pdf_sha256": "1" * 64,
                "question_pdf_sha256": "2" * 64,
                "items": [{"kind": "history", "id": "p40-r1", "spoken_text": text, "spoken_text_sha256": text_hash}]}
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps(manifest))
    generated = tmp_path / "generated"
    (generated / "audio").mkdir(parents=True)
    audio = generated / "audio" / f"{text_hash}.wav"
    wav = b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32
    audio.write_bytes(wav)
    report = {"schema_version": "v5-demo-audio-v1", "input_sha256": module.digest(source),
              "model_sha256": module.MODEL_SHA, "pilot_limit": 0,
              "records": [{"status": "generated", "spoken_text_sha256": text_hash,
                           "bytes": len(wav), "audio_sha256": module.digest(audio)}]}
    (generated / "run_records.json").write_text(json.dumps(report))
    destination = tmp_path / "installed"
    assert module.install(source, generated, destination) == 1
    index = json.loads((destination / "index.json").read_text())
    assert index["items"][0]["id"] == "p40-r1"
    assert (destination / index["items"][0]["filename"]).read_bytes() == wav
    audio.write_bytes(wav[:-1] + b"x")
    with pytest.raises(ValueError, match="integrity"):
        module.install(source, generated, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()
