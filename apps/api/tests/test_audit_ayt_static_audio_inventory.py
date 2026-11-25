import hashlib
from types import SimpleNamespace

from app.pipeline import audit_ayt_static_audio_inventory as subject


def test_inventory_checks_interface_with_resolver_id_and_marks_exam_unintegrated(tmp_path, monkeypatch):
    pack = tmp_path / "pack.json"
    pack.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(subject.AytHistoryExamPack, "model_validate_json", lambda _: SimpleNamespace())
    monkeypatch.setattr(subject, "build", lambda *_: {
        "summary": {"questions": 1, "units_with_digits_withheld": 0},
        "items": [{"kind": "interface", "id": "interface:unused", "static_role": "interface", "spoken_text": "Sonraki soru."},
                  {"kind": "question", "id": "q:stem", "static_role": "question_stem", "spoken_text": "Soru"}]})
    def resolve(_root, kind, identifier, text, source):
        assert kind == "interface" and source is None
        assert identifier == hashlib.sha256(text.encode()).hexdigest()
        return b"verified-audio"
    monkeypatch.setattr(subject, "_resolve_at", resolve)
    result = subject.audit(pack, [tmp_path])
    assert result["summary"]["interface"]["verified_audio"] == 1
    assert result["summary"]["question_stem"]["not_integrated"] == 1
