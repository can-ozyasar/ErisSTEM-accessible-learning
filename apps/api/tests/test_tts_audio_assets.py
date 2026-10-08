import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, demo_document, document_store
from app.pipeline.accessibility_reader import ReadingUnit
from app.pipeline.tts_audio_assets import (
    TtsAudioAssetManifest,
    resolve_verified_audio,
    sha256_text,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_document_store():
    document_store.reset_for_test(demo_document.model_dump(mode="json"))


def write_manifest(root: Path, *, text_hash: str) -> bytes:
    root.mkdir(parents=True)
    audio = b"private verified wav bytes"
    (root / "heading-1.wav").write_bytes(audio)
    payload = {
        "schema_version": "verified-tts-audio-assets-v1",
        "document_id": "synthetic-geometry-01",
        "published_revision": 1,
        "candidate": "candidate-a",
        "voice_profile": "turkish-test",
        "candidate_quality_report_sha256": "a" * 64,
        "listener_study_passed": True,
        "assets": [
            {
                "unit_id": "heading-1",
                "filename": "heading-1.wav",
                "spoken_text_sha256": text_hash,
                "audio_sha256": hashlib.sha256(audio).hexdigest(),
                "bytes": len(audio),
            }
        ],
    }
    (root / "assets.json").write_text(json.dumps(payload), encoding="utf-8")
    return audio


def test_verified_audio_endpoint_requires_matching_verified_spoken_text(tmp_path: Path, monkeypatch):
    audio_root = tmp_path / "student-audio"
    audio = write_manifest(audio_root / "synthetic-geometry-01", text_hash=sha256_text("Dik üçgende Pisagor bağıntısı"))
    monkeypatch.setenv("STUDENT_AUDIO_ROOT", str(audio_root))

    response = client.get(
        "/v1/student/documents/synthetic-geometry-01/audio/heading-1",
        headers={"X-Role": "student"},
    )

    assert response.status_code == 200
    assert response.content == audio
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["cache-control"] == "private, no-cache"


def test_audio_endpoint_blocks_a_stale_or_wrong_text_binding(tmp_path: Path, monkeypatch):
    audio_root = tmp_path / "student-audio"
    write_manifest(audio_root / "synthetic-geometry-01", text_hash="b" * 64)
    monkeypatch.setenv("STUDENT_AUDIO_ROOT", str(audio_root))

    response = client.get(
        "/v1/student/documents/synthetic-geometry-01/audio/heading-1",
        headers={"X-Role": "student"},
    )

    assert response.status_code == 404


def test_audio_manifest_requires_listener_study_before_any_asset_can_be_used():
    payload = {
        "schema_version": "verified-tts-audio-assets-v1",
        "document_id": "doc-1",
        "published_revision": 1,
        "candidate": "candidate-a",
        "voice_profile": "profile-a",
        "candidate_quality_report_sha256": "a" * 64,
        "listener_study_passed": False,
        "assets": [
            {
                "unit_id": "unit-1",
                "filename": "unit-1.wav",
                "spoken_text_sha256": "b" * 64,
                "audio_sha256": "c" * 64,
                "bytes": 1,
            }
        ],
    }

    with pytest.raises(ValueError, match="listener_study_required"):
        TtsAudioAssetManifest.model_validate(payload)


def test_audio_integrity_check_rejects_changed_wav(tmp_path: Path):
    root = tmp_path / "audio"
    write_manifest(root, text_hash=sha256_text("doğrulanmış metin"))
    manifest = TtsAudioAssetManifest.model_validate_json((root / "assets.json").read_text())
    (root / "heading-1.wav").write_bytes(b"altered")
    unit = ReadingUnit(
        id="heading-1",
        kind="heading",
        navigation_label="Başlık",
        spoken_text="doğrulanmış metin",
        braille_available=True,
        reading_order=1,
    )

    with pytest.raises(ValueError, match="audio_asset_integrity_mismatch"):
        resolve_verified_audio(
            manifest, root, document_id="synthetic-geometry-01", published_revision=1, unit=unit
        )
