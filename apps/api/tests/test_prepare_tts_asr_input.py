import hashlib
import importlib.util
import json
from pathlib import Path


def prepare_module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "prepare_tts_asr_input.py"
    spec = importlib.util.spec_from_file_location("prepare_tts_asr_input", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_prepare_asr_input_copies_only_checksum_bound_wavs_without_reference_text(tmp_path: Path, monkeypatch):
    module = prepare_module()
    private = tmp_path / "private"
    source = private / "download"
    audio_path = source / "private-audio" / "item-01.wav"
    audio_path.parent.mkdir(parents=True)
    audio_bytes = b"synthetic private wav"
    audio_path.write_bytes(audio_bytes)
    audio_hash = hashlib.sha256(audio_bytes).hexdigest()
    manifest = source / "download_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "kaggle-tts-audio-download-v1",
                "candidate": "voice-a",
                "files": [
                    {
                        "id": "item-01",
                        "path": "private-audio/item-01.wav",
                        "sha256": audio_hash,
                        "bytes": len(audio_bytes),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    run_records = private / "run_records.json"
    run_records.write_text(
        json.dumps(
            {
                "schema_version": "tts-synthesis-run-v1",
                "candidate": "voice-a",
                "records": [
                    {
                        "id": "item-01",
                        "kind": "formula",
                        "status": "generated",
                        "audio_sha256": audio_hash,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "private_root", lambda: private)

    output = private / "asr-input"
    report = module.prepare_asr_input(manifest, run_records, output)

    assert report == {
        "schema_version": "tts-asr-input-v1",
        "candidate": "voice-a",
        "audio_files": 1,
        "contains_reference_text": False,
    }
    prepared = json.loads((output / "tts-asr-input.json").read_text(encoding="utf-8"))
    assert prepared["assets"] == [
        {
            "id": "item-01",
            "kind": "formula",
            "audio_path": "audio/item-01.wav",
            "audio_sha256": audio_hash,
        }
    ]
    assert (output / "audio" / "item-01.wav").read_bytes() == audio_bytes
