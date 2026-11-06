from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ayt_tutor_routes import ayt_tutor_router


def client():
    app = FastAPI()
    app.include_router(ayt_tutor_router())
    return TestClient(app)


def question_payload():
    return {
        "id": "q-route-1", "stem": "Ulusal egemenlikle ilgili gelişmeyi bul.",
        "topic": "Millî Mücadele",
        "choices": [{"label": "A", "text": "TBMM'nin açılması"},
                    {"label": "B", "text": "Başka bir seçenek"}],
    }


def test_route_fails_closed_without_approved_graph(monkeypatch):
    monkeypatch.delenv("AYT_APPROVED_GRAPH_PATH", raising=False)
    monkeypatch.setenv("AYT_TTS_CACHE_ROOT", "/tmp/ayt-test-cache")
    response = client().post("/v1/ayt-tutor/turn", json={"question": question_payload()},
                             headers={"X-Role": "student"})
    assert response.status_code == 503


def test_route_rejects_answer_key_reference(monkeypatch):
    monkeypatch.setenv("AYT_APPROVED_GRAPH_PATH", "/tmp/not-used.json")
    monkeypatch.setenv("AYT_TTS_CACHE_ROOT", "/tmp/ayt-test-cache")
    payload = question_payload()
    payload["answer_key_ref"] = "private-key-1"
    response = client().post("/v1/ayt-tutor/turn", json={"question": payload},
                             headers={"X-Role": "student"})
    assert response.status_code == 422


def test_audio_endpoint_only_accepts_content_digest(monkeypatch, tmp_path: Path):
    digest = "a" * 64
    (tmp_path / f"{digest}.wav").write_bytes(b"RIFF" + b"0" * 20)
    monkeypatch.setenv("AYT_TTS_CACHE_ROOT", str(tmp_path))
    response = client().get(f"/v1/ayt-tutor/audio/{digest}", headers={"X-Role": "student"})
    assert response.status_code == 200
    assert client().get("/v1/ayt-tutor/audio/../secret", headers={"X-Role": "student"}).status_code in {404, 422}
