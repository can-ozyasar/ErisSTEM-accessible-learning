import hashlib
from types import SimpleNamespace

from app.pipeline import audit_ayt_static_audio_inventory as subject


def test_inventory_resolves_interface_and_exam_audio_with_exact_ids_and_pack_binding(tmp_path, monkeypatch):
    pack = tmp_path / "pack.json"
    pack.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(subject.AytHistoryExamPack, "model_validate_json", lambda _: SimpleNamespace())
    monkeypatch.setattr(subject, "build", lambda *_: {
        "summary": {"questions": 1, "static_units": 2, "units_with_digits_withheld": 0},
        "items": [{"kind": "interface", "id": "interface:unused", "static_role": "interface", "spoken_text": "Sonraki soru."},
                  {"kind": "question", "id": "q:stem", "static_role": "question_stem", "spoken_text": "Soru"}]})
    def resolve(_root, kind, identifier, text, source):
        if kind == "interface":
            assert source is None
            assert identifier == hashlib.sha256(text.encode()).hexdigest()
        else:
            assert kind == "question" and identifier == "q:stem"
            assert source == pack.resolve()
        return b"verified-audio"
    monkeypatch.setattr(subject, "_resolve_at", resolve)
    result = subject.audit(pack, [tmp_path])
    assert result["summary"]["interface"]["verified_audio"] == 1
    assert result["summary"]["question_stem"]["verified_audio"] == 1
    assert result["static_unit_count"] == result["verified_audio_count"] == 2
    assert result["missing_audio_count"] == 0
    assert result["verified_audio_fraction"] == 1.0
