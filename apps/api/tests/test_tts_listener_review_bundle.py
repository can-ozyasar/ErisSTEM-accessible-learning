import json
import wave
from pathlib import Path

import pytest

from app.pipeline.tts_audio_assets import sha256_file
from app.pipeline.tts_listener_review_bundle import build_review_bundle


def inputs(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "private-source"
    (root / "audio").mkdir(parents=True)
    audio = root / "audio" / "text-01.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24_000)
        wav.writeframes(b"\x00\x00" * 24_000)
    digest = sha256_file(audio)
    manifest = root / "tts-asr-input.json"
    manifest.write_text(json.dumps({
        "schema_version": "tts-asr-input-v1", "assets": [
            {"id": "text-01", "kind": "text", "audio_path": "audio/text-01.wav", "audio_sha256": digest}
        ],
    }), encoding="utf-8")
    packet = tmp_path / "reviewer.json"
    packet.write_text(json.dumps({
        "schema_version": "tts-listener-packet-v1", "study_id": "study-01", "reviewer_id": "reviewer-01",
        "items": [{"id": "text-01", "kind": "text", "audio_sha256": digest, "reference_spoken_text": "A < B"}],
    }), encoding="utf-8")
    return packet, manifest


def test_bundle_copies_only_verified_audio_and_escapes_private_reference(tmp_path: Path):
    packet, manifest = inputs(tmp_path)
    output = tmp_path / "private-bundle"
    report = build_review_bundle(packet, manifest, output)

    page = (output / "index.html").read_text(encoding="utf-8")
    assert report["review_items"] == 1
    assert "A &lt; B" in page
    assert "A < B" not in page
    assert (output / "audio" / "text-01.wav").is_file()
    assert "private-source" not in page
    with pytest.raises(FileExistsError):
        build_review_bundle(packet, manifest, output)


def test_bundle_refuses_tampered_audio_before_writing_output(tmp_path: Path):
    packet, manifest = inputs(tmp_path)
    (manifest.parent / "audio" / "text-01.wav").write_bytes(b"changed")
    output = tmp_path / "private-bundle"
    with pytest.raises(ValueError, match="review_audio_integrity_mismatch"):
        build_review_bundle(packet, manifest, output)
    assert not output.exists()


def test_bundle_refuses_path_traversal(tmp_path: Path):
    packet, manifest = inputs(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["assets"][0]["audio_path"] = "../outside.wav"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe_review_audio_path"):
        build_review_bundle(packet, manifest, tmp_path / "private-bundle")
