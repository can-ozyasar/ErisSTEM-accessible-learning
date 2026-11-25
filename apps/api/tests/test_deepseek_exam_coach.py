import json

import pytest

from app.deepseek_exam_coach import hint
from app.tutor_coach import CoachContext


def _context():
    return CoachContext(question_id="q", question_text="Olayın nedeni nedir?", choice_text="Yanlış seçenek",
                        section_title="Tarih", source_ids=["meb-1", "meb-2"],
                        evidence="primary: Kaynakta olayın nedeni açıklanıyor.\nrelation: İkinci kanıt sonucu gösteriyor.",
                        error_type="genel",
                        evidence_by_role={"primary": "Kaynakta olayın nedeni açıklanıyor.",
                                          "relation": "İkinci kanıt sonucu gösteriyor."})


def test_opt_in_uses_separate_judge_and_never_sends_correct_choice(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_COACH_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_SOURCE_PROCESSING_AUTHORIZED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    calls = []
    def fake(body, key, timeout):
        calls.append(body)
        assert key == "test-key" and timeout == 8
        assert "Kaynakta olayın nedeni açıklanıyor." in json.dumps(body, ensure_ascii=False)
        assert "İkinci kanıt sonucu gösteriyor." in json.dumps(body, ensure_ascii=False)
        assert "Gizli doğru metin" not in json.dumps(body, ensure_ascii=False)
        result = {"question": "Kaynakta neden olarak hangi ilişki anlatılıyor?"} if len(calls) == 1 else {"safe": True}
        return {"choices": [{"message": {"content": json.dumps(result, ensure_ascii=False)}}]}
    assert hint(_context(), "Karıştırdım", "Gizli doğru metin", request_fn=fake) is not None
    assert len(calls) == 2


def test_disabled_or_unsafe_model_falls_back(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_COACH_ENABLED", raising=False)
    assert hint(_context(), "", "Cevap", request_fn=lambda *_: pytest.fail("unexpected call")) is None
    monkeypatch.setenv("DEEPSEEK_COACH_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_SOURCE_PROCESSING_AUTHORIZED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    def unsafe(*_):
        return {"choices": [{"message": {"content": '{"question":"Doğru cevap A şıkkı mı?"}'}}]}
    assert hint(_context(), "", "Cevap", request_fn=unsafe) is None


def test_student_and_project_provider_opt_ins_do_not_override_missing_source_processing_authorization(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_COACH_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_SOURCE_PROCESSING_AUTHORIZED", "false")
    calls = []
    assert hint(_context(), "İki ilişkiyi karıştırdım.", "Gizli doğru metin",
                request_fn=lambda *args: calls.append(args)) is None
    assert calls == []
