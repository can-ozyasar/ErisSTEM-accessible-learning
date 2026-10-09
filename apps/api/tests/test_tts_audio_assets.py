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
    quality = {
        "report_type": "tts-quality-evaluation-v1", "contains_document_content": False,
        "quality_policy_version": "tts-quality-policy-v3", "evaluation_scope": "source-bound-release",
        "candidate": "candidate-a", "decision": "tts-candidate-kind-limited-listener-study-required",
        "eligible_kinds": ["text"], "gold_samples": 50,
        "kind_results": {"text": {"gold_samples": 10, "automatic_screen": "passed"}},
    }
    quality_bytes = json.dumps(quality).encode()
    (root / "quality_report.json").write_bytes(quality_bytes)
    quality_sha = hashlib.sha256(quality_bytes).hexdigest()
    listener = {
        "report_type": "tts-listener-study-evaluation-v1", "decision": "tts-listener-study-passed",
        "candidate": "candidate-a", "candidate_quality_report_sha256": quality_sha,
        "reviewers": 3, "malformed_reviewer_count": 0,
        "records": [{"kind": "text", "valid_reviews": 3, "all_match_reference": True, "all_intelligible": True, "serious_artifact_count": 0} for _ in range(10)],
    }
    listener_bytes = json.dumps(listener).encode()
    (root / "listener_report.json").write_bytes(listener_bytes)
    payload = {
        "schema_version": "verified-tts-audio-assets-v2",
        "document_id": "synthetic-geometry-01",
        "published_revision": 1,
        "candidate": "candidate-a",
        "voice_profile": "turkish-test",
        "candidate_quality_report_sha256": quality_sha,
        "listener_study_report_sha256": hashlib.sha256(listener_bytes).hexdigest(),
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
        "schema_version": "verified-tts-audio-assets-v2",
        "document_id": "doc-1",
        "published_revision": 1,
        "candidate": "candidate-a",
        "voice_profile": "profile-a",
        "candidate_quality_report_sha256": "a" * 64,
        "listener_study_report_sha256": "d" * 64,
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


def test_audio_endpoint_rejects_calibration_only_quality_report(tmp_path: Path, monkeypatch):
    root = tmp_path / "student-audio" / "synthetic-geometry-01"
    write_manifest(root, text_hash=sha256_text("Dik üçgende Pisagor bağıntısı"))
    quality_path = root / "quality_report.json"
    quality = json.loads(quality_path.read_text())
    quality["evaluation_scope"] = "calibration"
    quality_path.write_text(json.dumps(quality), encoding="utf-8")
    manifest_path = root / "assets.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["candidate_quality_report_sha256"] = hashlib.sha256(quality_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("STUDENT_AUDIO_ROOT", str(tmp_path / "student-audio"))
    response = client.get("/v1/student/documents/synthetic-geometry-01/audio/heading-1", headers={"X-Role": "student"})
    assert response.status_code == 404


def test_audio_endpoint_rejects_missing_listener_evidence(tmp_path: Path, monkeypatch):
    root = tmp_path / "student-audio" / "synthetic-geometry-01"
    write_manifest(root, text_hash=sha256_text("Dik üçgende Pisagor bağıntısı"))
    (root / "listener_report.json").unlink()
    monkeypatch.setenv("STUDENT_AUDIO_ROOT", str(tmp_path / "student-audio"))
    response = client.get("/v1/student/documents/synthetic-geometry-01/audio/heading-1", headers={"X-Role": "student"})
    assert response.status_code == 404
