import pytest

from app.tutor_authoring import create_drafts, review_draft
from app.tutor_dataset import CASES, TutorReviewInput, export_rows, validate_review_payload


def record(question_id, case):
    return {"question_id": question_id, "case": case, "error_type": "tarih", "source_ids": ["meb-1"],
            "evidence_quotes": ["Olay MÖ VI. yüzyılda gerçekleşmiştir."], "question_text": "Olay hangi tarihte gerçekleşti?",
            "learner_state": "Tarihi başka bir olayla karıştırdım.", "coaching_goal": "Öğrencinin sıralama yapması.",
            "guide_response": "Önce olayın hangi döneme ait olduğunu hatırlamaya çalışır mısın?",
            "early_answer_disclosed": False, "grounded_in_source": True, "simple_turkish": True,
            "age_appropriate": True, "reviewed_by": "Öğretmen", "approved": True}


def test_review_rejects_early_answer_and_non_source_quote():
    payload = {key: value for key, value in record("question-1", "soruyu_anlama").items() if key != "question_text"}
    item = TutorReviewInput(**{**payload, "guide_response": "Doğru cevap A şıkkı.",
                               "expected_revision": 0})
    with pytest.raises(ValueError, match="ifşa"):
        validate_review_payload(item, {"meb-1": "Olay MÖ VI. yüzyılda gerçekleşmiştir."})
    item = TutorReviewInput(**{**payload, "evidence_quotes": ["Başka metin."],
                               "expected_revision": 0})
    with pytest.raises(ValueError, match="birebir"):
        validate_review_payload(item, {"meb-1": "Olay MÖ VI. yüzyılda gerçekleşmiştir."})


def test_drafts_use_six_natural_coaching_cases_and_independent_rubric():
    drafts = create_drafts("Bu olay MÖ VI. yüzyılda ne zaman gerçekleşti?", [{"id": "meb-1", "text": "Olay MÖ VI. yüzyılda gerçekleşmiştir."}])
    assert [item["case"] for item in drafts] == list(CASES)
    assert all("hangi kavram" not in item["guide_response"] for item in drafts)
    assert all(review_draft(item)["passed"] for item in drafts)


def test_export_keeps_120_question_groups_and_short_evidence():
    records = [record(f"question-{number:03d}", case) for number in range(120) for case in CASES]
    rows, summary = export_rows(records)
    assert summary["question_groups"] == 120
    assert summary["examples"] == 720
    assert summary["splits"] == {"train": 504, "dev": 108, "sealed_test": 108}
    locations = {}
    for split, examples in rows.items():
        for example in examples:
            locations.setdefault(example["group_id"], set()).add(split)
            assert set(example) == {"group_id", "case", "error_type", "prompt", "completion"}
            assert "MEB kanıtı:" in example["prompt"]
            assert "answer_label" not in example["prompt"]
    assert all(len(value) == 1 for value in locations.values())
