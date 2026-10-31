from app.pipeline.tutor_qlora_readiness import assess
from app.tutor_dataset import CASES


def _record(question_id: str, case: str) -> dict:
    return {
        "question_id": question_id, "case": case, "error_type": "tarih", "source_ids": ["meb-1"],
        "evidence_quotes": ["Olay MÖ VI. yüzyılda gerçekleşmiştir."],
        "learner_state": "Tarihi başka bir olayla karıştırdım.", "coaching_goal": "Öğrencinin sıralama yapması.",
        "guide_response": "Önce olayın hangi döneme ait olduğunu hatırlamaya çalışır mısın?",
        "early_answer_disclosed": False, "grounded_in_source": True, "simple_turkish": True,
        "age_appropriate": True, "reviewed_by": "Öğretmen", "approved": True, "expected_revision": 0,
    }


def test_readiness_blocks_fewer_than_120_complete_groups_without_exposing_content():
    report = assess([_record("q-01", case) for case in CASES])
    assert report["status"] == "blocked"
    assert report["complete_question_groups"] == 1
    assert "120 tam onaylı soru grubu gerekli" in report["blocking_reasons"]
    assert "Olay MÖ" not in str(report)


def test_readiness_accepts_exactly_120_isolated_complete_question_groups():
    records = [_record(f"q-{number:03d}", case) for number in range(120) for case in CASES]
    report = assess(records)
    assert report["status"] == "ready"
    assert report["selected_split_question_groups"] == {"train": 84, "dev": 18, "sealed_test": 18}
    assert report["guarantees"]["answer_keys_included"] is False
