import pytest
from pydantic import ValidationError

from app.question_bank_structure import Question, navigation_units


BOX = {"page": 12, "bbox": (10, 20, 100, 40), "source_checksum": "a" * 64}


def question_payload():
    return {
        "id": "q-10", "number": 10, "source": BOX,
        "parts": [
            {"id": "q-10-stem", "kind": "stem", "text": "İlk ..... ve ikinci ..... hangi uygarlıktır?", "source": BOX,
             "blanks": [
                 {"number": 1, "marker": ".....", "source": BOX, "reviewed": True},
                 {"number": 2, "marker": ".....", "source": BOX, "reviewed": True},
             ]},
            {"id": "q-10-prompt", "kind": "prompt", "text": "Doğru sıralamayı seçiniz.", "source": BOX},
        ],
        "choices": [{"label": label, "text": text, "source": BOX} for label, text in
                    [("A", "Sümerler - Mısırlılar"), ("B", "Babiller - Çinliler"),
                     ("C", "Hititler - İranlılar"), ("D", "Yunanlar - Romalılar"),
                     ("E", "Hintler - Asurlular")]],
        "visuals": [], "status": "approved",
    }


def test_independent_question_parts_choices_and_numbered_blanks():
    question = Question.model_validate(question_payload())
    units = navigation_units(question)
    assert [unit["label"] for unit in units] == [
        "Soru 10", "Soru metni", "Soru kökü", "Şık A", "Şık B", "Şık C", "Şık D", "Şık E"]
    assert "1. boşluk" in units[1]["spoken_text"]
    assert "2. boşluk" in units[1]["spoken_text"]
    assert "1. boşluk" in question.model_dump()["parts"][0]["spoken_text"]
    assert units[3]["spoken_text"] == "Şık A: Sümerler - Mısırlılar"


def test_visual_without_reviewed_description_cannot_be_approved():
    payload = question_payload()
    payload["visuals"] = [{"id": "q-10-map", "kind": "map", "source": BOX}]
    with pytest.raises(ValidationError):
        Question.model_validate(payload)
    payload["status"] = "review_required"
    question = Question.model_validate(payload)
    assert navigation_units(question)[3]["spoken_text"] == "Görsel: Görsel betimlemesi doğrulanmadı."


def test_choices_must_be_separate_and_ordered():
    payload = question_payload()
    payload["choices"][1]["label"] = "C"
    with pytest.raises(ValidationError):
        Question.model_validate(payload)


def test_open_response_does_not_require_fake_choices():
    payload = question_payload()
    payload["question_type"] = "open_response"
    payload["choices"] = []
    question = Question.model_validate(payload)
    assert [unit["label"] for unit in navigation_units(question)] == ["Soru 10", "Soru metni", "Soru kökü"]
