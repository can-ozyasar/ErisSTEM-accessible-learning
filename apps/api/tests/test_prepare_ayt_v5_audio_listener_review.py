import hashlib
import json
from pathlib import Path

import pytest

from app.pipeline.prepare_ayt_v5_audio_listener_review import prepare
from app.pipeline.promote_ayt_v5_reviewed_audio import MODEL_SHA256


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fixture(tmp_path: Path):
    active_pack = b"active question pack"
    text = "Birinci soru. A şıkkı."
    text_hash = _digest(text.encode())
    input_payload = {
        "schema_version": "ayt-history-v5-static-audio-input-v1",
        "pack_checksum": _digest(active_pack),
        "voice_model_sha256": MODEL_SHA256,
        "items": [
            {"kind": "question", "id": "e1:stem", "static_role": "question_stem",
             "spoken_text": text, "spoken_text_sha256": text_hash, "contains_digits": False},
            {"kind": "question", "id": "e1:choice-a", "static_role": "choice",
             "spoken_text": text, "spoken_text_sha256": text_hash, "contains_digits": False},
        ],
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(input_payload, ensure_ascii=False), encoding="utf-8")
    candidate = tmp_path / "candidate"
    audio_dir = candidate / "audio"
    audio_dir.mkdir(parents=True)
    wav = b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32
    audio = audio_dir / f"{text_hash}.wav"
    audio.write_bytes(wav)
    rows = [
        {"kind": "question", "id": identity, "spoken_text_sha256": text_hash,
         "filename": f"audio/{text_hash}.wav", "bytes": len(wav), "audio_sha256": _digest(wav)}
        for identity in ("e1:stem", "e1:choice-a")
    ]
    index = {
        "schema_version": "v5-demo-installed-v1", "model_sha256": MODEL_SHA256,
        "source_sha256": {"question": input_payload["pack_checksum"]},
        "input_manifest_sha256": _digest(manifest.read_bytes()),
        "runtime_enabled": False, "requires_listening_review": True, "items": rows,
    }
    (candidate / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return manifest, candidate, input_payload


def test_prepares_local_accessible_review_for_exact_unique_audio(tmp_path: Path):
    manifest, candidate, payload = _fixture(tmp_path)
    page = candidate / "listener-review.html"

    assert prepare(manifest, candidate, page) == 1

    document = page.read_text(encoding="utf-8")
    assert "lang=\"tr\"" in document
    assert "Anlaşılabilirlik" in document
    assert "Onay yalnız seçtiğiniz WAV birimlerine uygulanır" in document
    assert "e1:stem" in document and "e1:choice-a" in document
    assert payload["pack_checksum"] in document
    assert "audio/" in document


def test_review_page_rejects_candidate_with_tampered_wav(tmp_path: Path):
    manifest, candidate, payload = _fixture(tmp_path)
    text_hash = payload["items"][0]["spoken_text_sha256"]
    (candidate / "audio" / f"{text_hash}.wav").write_bytes(b"tampered")

    with pytest.raises(ValueError, match="candidate_audio_checksum_mismatch"):
        prepare(manifest, candidate, candidate / "listener-review.html")


def test_review_page_must_remain_inside_private_candidate_folder(tmp_path: Path):
    manifest, candidate, _ = _fixture(tmp_path)

    with pytest.raises(ValueError, match="review_page_must_be_inside_private_candidate_root"):
        prepare(manifest, candidate, tmp_path / "public-review.html")
