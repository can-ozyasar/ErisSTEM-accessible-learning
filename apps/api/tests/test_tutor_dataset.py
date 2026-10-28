import pytest

from app.tutor_dataset import REVIEW_STAGES, TutorReviewInput, export_rows, validate_review_payload


def record(question_id, stage):
    return {"question_id": question_id, "stage": stage, "source_ids": ["meb-1"],
            "guide_response": "Kaynağın anlattığı kavramla soru kökündeki ifadeyi ilişkilendirir misin?",
            "early_answer_disclosed": False, "grounded_in_source": True, "simple_turkish": True,
            "reviewed_by": "Öğretmen", "approved": True}


def test_review_rejects_early_answer_and_unknown_source():
    item = TutorReviewInput(**{**record("question-1", "soru_analizi"), "guide_response": "Doğru cevap A şıkkı.",
                               "expected_revision": 0})
    with pytest.raises(ValueError, match="ifşa"):
        validate_review_payload(item, {"meb-1"})
    item = TutorReviewInput(**{**record("question-1", "soru_analizi"), "source_ids": ["other"],
                               "expected_revision": 0})
    with pytest.raises(ValueError, match="getirme"):
        validate_review_payload(item, {"meb-1"})


def test_export_keeps_question_groups_and_excludes_source_material():
    records = [record(f"question-{number:02d}", stage) for number in range(60) for stage in REVIEW_STAGES]
    rows, summary = export_rows(records)
    assert summary["question_groups"] == 60
    assert summary["examples"] == 180
    assert summary["splits"] == {"train": 126, "dev": 27, "sealed_test": 27}
    locations = {}
    for split, examples in rows.items():
        for example in examples:
            locations.setdefault(example["group_id"], set()).add(split)
            assert set(example) == {"group_id", "stage", "prompt", "completion"}
            assert "MEB kanıtı çalışma anında" in example["prompt"]
    assert all(len(value) == 1 for value in locations.values())
