import hashlib
from types import SimpleNamespace

import pytest

from app.pipeline import evaluate_deepseek_exam_dev as subject


def test_probe_uses_development_only_and_records_no_question_text(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    identifier = "dev-question"
    qid = "licensed-" + hashlib.sha256(identifier.encode()).hexdigest()[:20]
    question = SimpleNamespace(id=qid, question="Gizli soru metni", choices=["A", "B"], correct_label="A", topic="Tarih",
                               evidence=[SimpleNamespace(source_id="meb", quote="Gizli kaynak metni")])
    pack = SimpleNamespace(questions=[question], licensed_question_source_checksum="q")
    monkeypatch.setattr(subject.AytHistoryExamPack, "model_validate", lambda _: pack)
    monkeypatch.setattr(subject, "hint", lambda *_, **__: "Nasıl düşünürsün?")
    split = {"schema": "ogm-ayt-source-grounded-research-split-v1", "source_checksum": "q",
             "splits": {identifier: "development", "sealed-question": "sealed_test"}}
    result = subject.evaluate({}, split, limit=1)
    assert result["count"] == result["accepted_by_guard"] == 1
    assert "Gizli soru" not in str(result) and "Gizli kaynak" not in str(result)
    assert all(row["candidate_id"] != "sealed-question" for row in result["rows"])
    with pytest.raises(ValueError, match="sınırı"):
        subject.evaluate({}, split, limit=14)
