import pytest

from app.tutor_authoring import create_drafts, review_draft
from app.tutor_dataset import (
    CASES,
    CONCEPT_KEYS_SOURCE,
    TutorReviewInput,
    derive_concept_keys,
    export_rows,
    split_question_ids,
    validate_review_payload,
)


def record(question_id, case):
    number = int(question_id.rsplit("-", 1)[-1])
    return {"question_id": question_id, "case": case, "error_type": "tarih", "source_ids": ["meb-1"],
            "evidence_quotes": ["Olay MÖ VI. yüzyılda gerçekleşmiştir."], "question_text": "Olay hangi tarihte gerçekleşti?",
            "concept_keys": [f"topic:{number % 6}", f"event:{question_id}"],
            "concept_keys_source": CONCEPT_KEYS_SOURCE,
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


def test_question_analysis_can_ask_without_evidence_but_later_stages_cannot():
    early = {key: value for key, value in record("question-1", "soruyu_anlama").items()
             if key != "question_text"}
    early.update({"source_ids": [], "evidence_quotes": [], "expected_revision": 0})
    validate_review_payload(TutorReviewInput(**early), {})
    later = {**early, "case": "kanitla_bag_kur"}
    with pytest.raises(ValueError, match="kaynak gerekli"):
        validate_review_payload(TutorReviewInput(**later), {})


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
    assert sum(summary["splits"].values()) == 720
    assert all(summary["splits"][split] > 0 for split in ("train", "dev", "sealed_test"))
    assert summary["split_strategy"] == "transitive_concept_components_v1"
    locations = {}
    for split, examples in rows.items():
        for example in examples:
            locations.setdefault(example["group_id"], set()).add(split)
            assert set(example) == {"group_id", "case", "error_type", "prompt", "completion"}
            assert "MEB kanıtı:" in example["prompt"]
            assert "answer_label" not in example["prompt"]
    assert all(len(value) == 1 for value in locations.values())


def test_export_omits_empty_evidence_line_for_opening_stage():
    records = [record(f"question-{number:03d}", case) for number in range(120) for case in CASES]
    for row in records:
        if row["case"] in CASES[:2]:
            row["source_ids"] = []
            row["evidence_quotes"] = []
    rows, _ = export_rows(records)
    examples = [row for split in rows.values() for row in split]
    assert all("MEB kanıtı:" not in row["prompt"] for row in examples if row["case"] in CASES[:2])
    assert all("MEB kanıtı:" in row["prompt"] for row in examples if row["case"] not in CASES[:2])


def test_concept_split_keeps_shared_and_transitively_shared_concepts_together():
    ids = [f"question-{number:03d}" for number in range(120)]
    concepts = {question_id: [f"unique:{question_id}"] for question_id in ids}
    concepts[ids[0]] = ["event:shared-a", "unique:0"]
    concepts[ids[1]] = ["event:shared-a", "event:shared-b"]
    concepts[ids[2]] = ["event:shared-b", "unique:2"]
    split = split_question_ids(ids, concepts)
    assert split[ids[0]] == split[ids[1]] == split[ids[2]]


def test_export_requires_server_attested_graph_concepts():
    records = [record(f"question-{number:03d}", case) for number in range(120) for case in CASES]
    records[0]["concept_keys_source"] = "client_supplied"
    with pytest.raises(ValueError, match="sunucuda türetilmiş"):
        export_rows(records)


def test_split_concepts_come_only_from_approved_graph_edges():
    graph = {"approved": True, "nodes": [{"id": "tbmm", "label": "TBMM"}],
             "edges": [{"approved": True, "from_node": "tbmm", "to_node": "meclis-acildi"},
                       {"approved": False, "from_node": "ignored", "to_node": "node"}]}
    assert derive_concept_keys(graph) == ["node:meclis-acildi", "node:tbmm"]
    assert derive_concept_keys({**graph, "approved": False}) == []
