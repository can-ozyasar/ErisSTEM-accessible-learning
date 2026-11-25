import hashlib
from types import SimpleNamespace

import pymupdf
import pytest

from app.pipeline import audit_ogm_pilot_question_integrity as subject


def test_question_and_key_changes_are_reported(tmp_path, monkeypatch):
    path = tmp_path / "source.pdf"
    doc = pymupdf.open(); page = doc.new_page()
    page.insert_text((72, 100), "Tarih sorusu A B C D E")
    doc.save(path); doc.close()
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    identifier = "candidate"
    pid = "licensed-" + hashlib.sha256(identifier.encode()).hexdigest()[:20]
    location = {"source_checksum": checksum, "page": 1, "bbox": [60, 60, 400, 130]}
    parts = [{"text": "Tarih sorusu", "source": location}]
    choices = [{"label": label, "text": label, "source": location} for label in "ABCDE"]
    question = SimpleNamespace(id=pid, question="Tarih sorusu", choices=list("ABCDE"), correct_label="A", review_method="license_bound_pdf_crop_review")
    monkeypatch.setattr(subject.AytHistoryExamPack, "model_validate", lambda _: SimpleNamespace(licensed_question_source_checksum=checksum, questions=[question]))
    candidates = {"schema": "ayt-target-question-candidates-v1", "source_checksum": checksum,
                  "rows": [{"candidate_id": identifier, "question": {"parts": parts, "choices": choices}}]}
    answers = {"schema": "ogm-ayt-history-answer-key-v1", "source_checksum": checksum,
               "records": [{"candidate_id": identifier, "correct_choice": "A"}]}
    assert subject.audit({}, candidates, answers, path)["requires_review_count"] == 0
    question.correct_label = "B"
    assert subject.audit({}, candidates, answers, path)["requires_review_count"] == 1
    answers["source_checksum"] = "wrong"
    with pytest.raises(ValueError, match="kaynağı uyuşmuyor"):
        subject.audit({}, candidates, answers, path)
