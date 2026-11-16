from app.pipeline.tutor_qlora_readiness import assess
from app.tutor_dataset import CASES, CONCEPT_KEYS_SOURCE


def _record(question_id: str, case: str) -> dict:
    return {
        "question_id": question_id, "case": case, "error_type": "tarih", "source_ids": ["meb-1"],
        "evidence_quotes": ["Olay MÖ VI. yüzyılda gerçekleşmiştir."],
        "concept_keys": [f"topic:{int(question_id.split('-')[-1]) % 6}", f"event:{question_id}"],
        "concept_keys_source": CONCEPT_KEYS_SOURCE,
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
    splits = report["selected_split_question_groups"]
    assert sum(splits.values()) == 120
    assert all(splits[key] > 0 for key in ("train", "dev", "sealed_test"))
    assert report["split_strategy"] == "transitive_concept_components_v1"
    assert report["guarantees"]["answer_keys_included"] is False


def test_readiness_blocks_when_concept_components_cannot_form_three_splits():
    records = [_record(f"q-{number:03d}", case) for number in range(120) for case in CASES]
    for row in records:
        row["concept_keys"] = ["one-connected-component"]
    report = assess(records)
    assert report["status"] == "blocked"
    assert sum(report["selected_split_question_groups"].values()) == 0
    assert report["guarantees"]["question_group_split_isolated"] is False


def test_readiness_rejects_client_like_concept_keys_without_server_attestation():
    records = [_record(f"q-{number:03d}", case) for number in range(120) for case in CASES]
    for row in records:
        row["concept_keys_source"] = "client_supplied"
    report = assess(records)
    assert report["status"] == "blocked"
    assert "onaylı graf ilişkisinden sunucuda üretilmiş kavram anahtarı yok" in report["blocking_reasons"]
