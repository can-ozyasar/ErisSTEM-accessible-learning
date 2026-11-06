from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ayt_knowledge_graph import DialogueStage, TutorDialogueState
from app.ayt_tutor_routes import AytTutorReply, ayt_tutor_router


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


def test_route_returns_state_text_and_cache_id_with_local_runtime(monkeypatch, tmp_path: Path):
    audio = tmp_path / ("b" * 64 + ".wav")
    audio.write_bytes(b"RIFF" + b"0" * 20)

    class FakeRuntime:
        def __init__(self):
            self.last_timings = {"retrieval": 2, "first_token": 4, "llm": 8, "tts": 1, "total": 15}

        def start(self, question, state, learner_message):
            assert question.answer_key_ref is None
            assert learner_message == "Bir ipucu ver"
            return (TutorDialogueState(session_id="route-session", question_id=question.id,
                                       stage=DialogueStage.HATIRLAMAYI_ORTAYA_CIKARMA),
                    "Kaynakta hangi ayrıntıyı hatırlıyorsun?", [audio])

    monkeypatch.setenv("AYT_APPROVED_GRAPH_PATH", "/private/approved-graph.json")
    monkeypatch.setenv("AYT_TTS_CACHE_ROOT", str(tmp_path))
    monkeypatch.setattr("app.ayt_tutor_routes._configured_runtime", lambda *_args: FakeRuntime())
    response = client().post("/v1/ayt-tutor/turn",
                             json={"question": question_payload(), "learner_message": "Bir ipucu ver"},
                             headers={"X-Role": "student"})
    assert response.status_code == 200
    body = response.json()
    assert body["text"].startswith("Kaynakta")
    assert body["audio_ids"] == ["b" * 64]
    assert body["state"]["stage"] == "hatirlamayi_ortaya_cikarma"
    assert body["timings_ms"]["first_token"] == 4


def test_route_rejects_invalid_timing_contract():
    payload = {"state": {"session_id": "session-1", "question_id": "q-route-1"},
               "text": "Soru?", "audio_ids": [], "timings_ms": {"other": 1}}
    response = client().post("/v1/ayt-tutor/turn", json={"question": question_payload()},
                             headers={"X-Role": "student"})
    # The public request does not accept response fields; the direct model
    # validation below covers the contract without enabling runtime config.
    with pytest.raises(ValueError, match="Geçersiz tutor"):
        AytTutorReply.model_validate(payload)
    assert response.status_code == 503
