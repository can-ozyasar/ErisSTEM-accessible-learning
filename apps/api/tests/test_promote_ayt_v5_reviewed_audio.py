import hashlib
import json
from pathlib import Path

import pytest

from app.demo_audio import resolve_demo_audio
from app.pipeline.promote_ayt_v5_reviewed_audio import MODEL_SHA256, promote


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fixture(tmp_path: Path):
    active_pack = tmp_path / "active-pack.json"
    active_pack.write_bytes(b"exact active pack")
    source = {
        "schema_version": "ayt-history-v5-static-audio-input-v1",
        "pack_checksum": _digest(active_pack.read_bytes()),
        "voice_model_sha256": MODEL_SHA256,
        "items": [],
    }
    texts = ["Birinci soru. Seçenek A.", "İkinci soru. Seçenek B."]
    for index, text in enumerate(texts, start=1):
        source["items"].append({
            "kind": "question",
            "id": f"q{index}:stem",
            "spoken_text": text,
            "spoken_text_sha256": _digest(text.encode()),
            "contains_digits": False,
        })
    input_manifest = tmp_path / "manifest.json"
    input_manifest.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    candidate = tmp_path / "candidate"
    (candidate / "audio").mkdir(parents=True)
    wavs = {}
    candidate_items = []
    for item in source["items"]:
        text_hash = item["spoken_text_sha256"]
        wav = b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32
        audio_path = candidate / "audio" / f"{text_hash}.wav"
        audio_path.write_bytes(wav)
        wavs[text_hash] = wav
        candidate_items.append({
            "kind": item["kind"], "id": item["id"],
            "spoken_text_sha256": text_hash,
            "filename": f"audio/{text_hash}.wav",
            "bytes": len(wav), "audio_sha256": _digest(wav),
        })
    candidate_index = {
        "schema_version": "v5-demo-installed-v1",
        "model_sha256": MODEL_SHA256,
        "source_sha256": {"question": source["pack_checksum"]},
        "input_manifest_sha256": _digest(input_manifest.read_bytes()),
        "runtime_enabled": False,
        "requires_listening_review": True,
        "items": candidate_items,
    }
    (candidate / "index.json").write_text(json.dumps(candidate_index), encoding="utf-8")
    review = {
        "schema": "ayt-v5-human-listener-review-v1",
        "source_pack_sha256": source["pack_checksum"],
        "input_manifest_sha256": _digest(input_manifest.read_bytes()),
        "voice_model_sha256": MODEL_SHA256,
        "reviewer": "reviewer-01",
        "reviewed_at_utc": "2026-11-25T12:00:00Z",
        "items": [
            {"spoken_text_sha256": source["items"][0]["spoken_text_sha256"],
             "intelligibility": "pass", "pronunciation": "pass", "audio_artifacts": "none", "decision": "accept"},
            {"spoken_text_sha256": source["items"][1]["spoken_text_sha256"],
             "intelligibility": "pass", "pronunciation": "fail", "audio_artifacts": "none", "decision": "reject"},
        ],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    return active_pack, input_manifest, candidate, review_path, source, wavs


def test_promotion_enables_only_explicitly_approved_exact_audio(tmp_path, monkeypatch):
    active_pack, input_manifest, candidate, review, source, wavs = _fixture(tmp_path)
    destination = tmp_path / "approved"

    assert promote(input_manifest, candidate, review, destination) == 1

    index = json.loads((destination / "index.json").read_text(encoding="utf-8"))
    accepted = source["items"][0]
    rejected = source["items"][1]
    assert index["runtime_enabled"] is True
    assert index["requires_listening_review"] is False
    assert index["listener_review"]["approved_unique_texts"] == 1
    assert [item["spoken_text_sha256"] for item in index["items"]] == [accepted["spoken_text_sha256"]]
    monkeypatch.setenv("LOCAL_TTS_DEMO_ROOT", str(destination))
    assert resolve_demo_audio("question", accepted["id"], accepted["spoken_text"], active_pack) == wavs[accepted["spoken_text_sha256"]]
    assert resolve_demo_audio("question", rejected["id"], rejected["spoken_text"], active_pack) is None


def test_promotion_rejects_review_not_bound_to_exact_input(tmp_path):
    _, input_manifest, candidate, review, _, _ = _fixture(tmp_path)
    payload = json.loads(review.read_text(encoding="utf-8"))
    payload["input_manifest_sha256"] = "0" * 64
    review.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="listener_review_binding_mismatch"):
        promote(input_manifest, candidate, review, tmp_path / "approved")


def test_promotion_rejects_acceptance_with_pronunciation_failure(tmp_path):
    _, input_manifest, candidate, review, _, _ = _fixture(tmp_path)
    payload = json.loads(review.read_text(encoding="utf-8"))
    payload["items"][1]["decision"] = "accept"
    review.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="accept_requires_all_quality_checks_to_pass"):
        promote(input_manifest, candidate, review, tmp_path / "approved")


def test_promotion_rejects_tampered_candidate_wav(tmp_path):
    _, input_manifest, candidate, review, source, _ = _fixture(tmp_path)
    text_hash = source["items"][0]["spoken_text_sha256"]
    (candidate / "audio" / f"{text_hash}.wav").write_bytes(b"tampered")

    with pytest.raises(ValueError, match="candidate_audio_checksum_mismatch"):
        promote(input_manifest, candidate, review, tmp_path / "approved")
