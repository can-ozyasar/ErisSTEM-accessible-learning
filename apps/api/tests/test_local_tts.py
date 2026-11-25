import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient

from app import local_tts, main


class FakeHeaders:
    def __init__(self, content_type: str = "audio/wav"):
        self.content_type = content_type

    def get_content_type(self):
        return self.content_type


class FakeResponse:
    def __init__(self, body: bytes = b"R" * 44, content_type: str = "audio/wav"):
        self.body = body
        self.headers = FakeHeaders(content_type)

    def read(self, _: int):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_local_tts_only_accepts_internal_http_endpoint(monkeypatch):
    monkeypatch.delenv("LOCAL_TTS_URL", raising=False)
    assert local_tts.local_tts_url() is None
    monkeypatch.setenv("LOCAL_TTS_URL", "https://external.example/synthesize")
    assert local_tts.local_tts_url() is None
    monkeypatch.setenv("LOCAL_TTS_URL", "http://tts:5000/synthesize")
    assert local_tts.local_tts_url() == "http://tts:5000/synthesize"


def test_local_tts_rejects_bad_audio_and_network_failures(monkeypatch):
    monkeypatch.setenv("LOCAL_TTS_URL", "http://tts:5000/synthesize")
    monkeypatch.setattr(local_tts, "urlopen", lambda *_args, **_kwargs: FakeResponse(b"bad"))
    with pytest.raises(local_tts.LocalTtsUnavailable):
        local_tts.synthesize_verified_text("Doğrulanmış metin")
    monkeypatch.setattr(local_tts, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("down")))
    with pytest.raises(local_tts.LocalTtsUnavailable):
        local_tts.synthesize_verified_text("Doğrulanmış metin")


def test_local_tts_accepts_piper_wav_when_its_content_type_is_wrong(monkeypatch):
    monkeypatch.setenv("LOCAL_TTS_URL", "http://tts:5000/synthesize")
    piper_wav = b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32
    monkeypatch.setattr(local_tts, "urlopen", lambda *_args, **_kwargs: FakeResponse(piper_wav, "text/html"))
    assert local_tts.synthesize_verified_text("Doğrulanmış metin") == piper_wav


def test_verified_audio_is_reused_from_private_local_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_TTS_CACHE_ROOT", str(tmp_path))
    calls = []
    wav = b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32
    monkeypatch.setattr(local_tts, "synthesize_verified_text", lambda text: calls.append(text) or wav)
    assert local_tts.synthesize_cached_verified_text("Doğrulanmış metin") == wav
    assert local_tts.synthesize_cached_verified_text("Doğrulanmış metin") == wav
    assert calls == ["Doğrulanmış metin"]


def test_voice_change_does_not_reuse_other_models_cached_audio(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_TTS_CACHE_ROOT", str(tmp_path))
    calls = []
    wav = b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32
    monkeypatch.setattr(local_tts, "synthesize_verified_text", lambda text: calls.append(text) or wav)
    monkeypatch.setenv("LOCAL_TTS_VOICE_CACHE_VERSION", "piper")
    local_tts.synthesize_cached_verified_text("aynı metin")
    monkeypatch.setenv("LOCAL_TTS_VOICE_CACHE_VERSION", "v5")
    local_tts.synthesize_cached_verified_text("aynı metin")
    local_tts.synthesize_cached_verified_text("aynı metin")
    assert calls == ["aynı metin", "aynı metin"]


def test_concurrent_requests_for_same_speech_share_one_synthesis(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_TTS_CACHE_ROOT", str(tmp_path))
    started, release = Event(), Event()
    calls = []
    wav = b"RIFF" + b"0" * 4 + b"WAVE" + b"0" * 32

    def synthesize(text):
        calls.append(text)
        started.set()
        assert release.wait(timeout=5)
        return wav

    monkeypatch.setattr(local_tts, "synthesize_verified_text", synthesize)
    with ThreadPoolExecutor(max_workers=8) as executor:
        requests = [executor.submit(local_tts.synthesize_cached_verified_text, "Ortak cümle") for _ in range(8)]
        assert started.wait(timeout=5)
        release.set()
        assert all(request.result(timeout=5) == wav for request in requests)
    assert calls == ["Ortak cümle"]


def test_history_audio_uses_one_turkish_voice_for_entire_sentence(monkeypatch):
    received = []
    monkeypatch.setattr(local_tts, "synthesize_verified_text", lambda text: received.append(text) or b"RIFF0000WAVE")
    audio = local_tts.synthesize_history_text("MÖ VI. yüzyıl, Metropolitan Art Museum, New York. Antik Yunan.")
    assert audio == b"RIFF0000WAVE"
    assert received == ["Milattan önce altıncı yüzyıl, Metropoliten Art Müziyum, New York. Antik Yunan."]


def test_student_local_audio_uses_only_reviewed_reading_unit(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setenv("LOCAL_TTS_URL", "http://tts:5000/synthesize")
    received = []

    def fake_synthesize(text: str):
        received.append(text)
        return b"R" * 44

    monkeypatch.setattr(main, "synthesize_cached_verified_text", fake_synthesize)
    response = client.get(
        "/v1/student/documents/synthetic-geometry-01/local-audio/heading-1",
        headers={"X-Role": "student"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert received == ["Dik üçgende Pisagor bağıntısı"]
    missing = client.get(
        "/v1/student/documents/synthetic-geometry-01/local-audio/not-a-unit",
        headers={"X-Role": "student"},
    )
    assert missing.status_code == 404


def test_interface_exploration_speech_is_short_local_only_and_ephemeral(monkeypatch):
    client = TestClient(main.app)
    spoken = []
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(main, "synthesize_verified_text", lambda text: spoken.append(text) or b"R" * 44)
    response = client.post("/v1/student/interface-speech", json={"text": "  Tarih   kitabı, düğme  "}, headers={"X-Role": "student"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["cache-control"] == "no-store"
    assert spoken == ["Tarih kitabı, düğme"]
    assert client.post("/v1/student/interface-speech", json={"text": "x" * 601}, headers={"X-Role": "student"}).status_code == 422
    monkeypatch.setenv("APP_ENV", "production")
    assert client.post("/v1/student/interface-speech", json={"text": "Düğme"}, headers={"X-Role": "student"}).status_code == 503
    assert spoken == ["Tarih kitabı, düğme"]


def test_private_review_audio_requires_an_exact_finetuned_v5_asset(tmp_path, monkeypatch):
    review = tmp_path / "review"
    review.mkdir()
    checksum = "a" * 64
    (review / "manifest.json").write_text(json.dumps({
        "schema": "ayt-history-human-pdf-crop-review-template-v1",
        "candidate_checksum": checksum,
        "reviews": [{"id": "authoring-001"}],
    }), encoding="utf-8")
    pack = tmp_path / "candidates.json"
    pack.write_text(json.dumps({
        "schema": "ayt-history-original-question-candidate-pack-v1",
        "candidate_checksum": checksum,
        "questions": [{"id": "authoring-001", "spoken_question": "Doğrulanmış soru."}],
    }), encoding="utf-8")
    monkeypatch.setattr(main, "_REVIEW_ROOT", review)
    monkeypatch.setattr(main, "_REVIEW_CANDIDATE_PACK", pack)
    monkeypatch.setenv("APP_ENV", "development")
    received = []
    monkeypatch.setattr(main, "resolve_demo_audio", lambda kind, item_id, text: received.append((kind, item_id, text)) or b"R" * 44)
    client = TestClient(main.app)
    response = client.post("/v1/review/ayt-history/audio/authoring-001", headers={"X-Role": "reviewer"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert received == [("question", "authoring-001", "Doğrulanmış soru.")]
    monkeypatch.setattr(main, "resolve_demo_audio", lambda *_: None)
    assert client.post("/v1/review/ayt-history/audio/authoring-001", headers={"X-Role": "reviewer"}).status_code == 503
