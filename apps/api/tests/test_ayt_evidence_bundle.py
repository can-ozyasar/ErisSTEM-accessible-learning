import pytest

from app.pipeline.ayt_evidence_bundle import build


def _chunk(chunk_id: str, text: str, page: int) -> dict:
    return {
        "id": chunk_id, "section_id": "1.1", "section_title": "İlk Türk devletleri", "page": page,
        "bbox": [1, 2, 3, 4], "text": text,
        "pre_review": {"decision": "review_for_approval"}, "quality": {"warnings": []},
    }


def _inputs():
    questions = {"schema": "ayt-tarih2-candidates-v1", "source_checksum": "questions-v1", "candidates": [{
        "candidate_id": "q1", "exam_year": 2024, "year_status": "bound",
    }]}
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "corpus-v1", "books": [{
        "grade": 9, "source_name": "history.pdf", "source_checksum": "book-v1", "index": {"chunks": [
            _chunk("core", "Kurultay devlet meselelerinin görüşüldüğü meclisti.", 8),
            _chunk("relation", "Hatun devlet işlerinde söz sahibi olabilirdi.", 9),
            _chunk("noise", "Kurultayda toylar düzenlenirdi ve eğlenceler yapılırdı.", 10),
        ]},
    }]}
    plan = {"schema": "ayt-evidence-plans-v1", "question_source_checksum": "questions-v1",
            "corpus_checksum": "corpus-v1", "cases": [{"candidate_id": "q1",
            "topic_labels": ["ilk türk devletleri"], "claims": [
                {"id": "kurultay-islev", "role": "primary", "required": True,
                 "all_of": ["kurultay", "meclis"], "query_terms": ["devlet meseleleri"],
                 "section_hints": ["ilk türk"]},
                {"id": "hatun-devlet", "role": "relation", "required": True,
                 "all_of": ["hatun", "devlet"], "query_terms": ["söz sahibi"]},
            ]}]}
    return questions, corpus, plan


def test_bundle_requires_each_teacher_planned_claim():
    questions, corpus, plan = _inputs()
    result = build(questions, corpus, plan, per_claim=2)
    row = result["proposals"][0]
    assert row["status"] == "teacher_review_required"
    assert row["evidence_plan"]["complete"] is True
    assert {item["claim_id"] for item in row["suggestions"]} == {"kurultay-islev", "hatun-devlet"}
    assert len(row["suggestions"]) == 2


def test_bundle_abstains_when_one_required_relationship_has_no_source():
    questions, corpus, plan = _inputs()
    corpus["books"][0]["index"]["chunks"] = corpus["books"][0]["index"]["chunks"][:1]
    row = build(questions, corpus, plan)["proposals"][0]
    assert row["status"] == "reretrieve_required"
    assert row["evidence_plan"]["missing_claim_ids"] == ["hatun-devlet"]


def test_bundle_is_variable_sized_and_keeps_page_diverse_alternatives():
    questions, corpus, plan = _inputs()
    corpus["books"][0]["index"]["chunks"].append(
        _chunk("core-alternate", "Kurultay bir meclis olarak devlet meselelerini görüşürdü.", 11)
    )
    result = build(questions, corpus, plan, per_claim=2)
    core = [item for item in result["proposals"][0]["suggestions"] if item["claim_id"] == "kurultay-islev"]
    assert {item["page"] for item in core} == {8, 11}
    assert len(result["proposals"][0]["suggestions"]) == 3


def test_bundle_rejects_unbound_or_underspecified_plan():
    questions, corpus, plan = _inputs()
    plan["cases"][0]["claims"][0]["all_of"] = []
    with pytest.raises(ValueError, match="en az bir arama dayanağı"):
        build(questions, corpus, plan)


def test_bundle_accepts_full_teacher_schema_and_uses_explicit_support_gate():
    questions, corpus, plan = _inputs()
    case = plan["cases"][0]
    case["evidence_claims"] = case.pop("claims")
    for claim in case["evidence_claims"]:
        claim["claim_type"] = "person_event" if claim["role"] == "relation" else "definition"
        claim["stage_min"] = "evidence_link"
        claim["must_support"] = False
    case["option_discriminators"] = [{
        "id": "actor", "claim_ids": ["hatun-devlet"], "required_for_decision": True,
    }]
    case["support_requirements"] = {
        "all_must_support_claim_ids": ["kurultay-islev"],
        "required_discriminator_ids": ["actor"],
    }
    case["abstain_gate"] = {"when_any_required_claim_uncovered": True, "outcome": "reretrieve"}
    corpus["books"][0]["index"]["chunks"] = corpus["books"][0]["index"]["chunks"][:1]
    row = build(questions, corpus, plan)["proposals"][0]
    assert row["status"] == "teacher_review_required"
    assert row["evidence_plan"]["required_claim_ids"] == ["kurultay-islev"]
    assert row["evidence_plan"]["option_discriminators"][0]["id"] == "actor"


def test_bundle_interprets_nested_agent_groups_as_separate_required_groups():
    questions, corpus, plan = _inputs()
    claim = plan["cases"][0]["claims"][0]
    claim["all_of_groups"] = [["Kurultay"], [["meclis"], ["devlet meseleleri"]]]
    row = build(questions, corpus, plan)["proposals"][0]
    assert row["status"] == "teacher_review_required"


def test_bundle_accepts_only_explicit_teacher_claim_type_aliases():
    questions, corpus, plan = _inputs()
    plan["cases"][0]["claims"][0]["claim_type"] = "event_origin"
    assert build(questions, corpus, plan)["proposals"][0]["status"] == "teacher_review_required"
    plan["cases"][0]["claims"][0]["claim_type"] = "made_up_relation"
    with pytest.raises(ValueError, match="iddiası türü"):
        build(questions, corpus, plan)


def test_bundle_uses_teacher_hard_section_filter_only_for_discovery():
    questions, corpus, plan = _inputs()
    corpus["books"][0]["index"]["chunks"].append(_chunk(
        "matching-section", "Kurultay bir meclis olarak devlet meselelerini görüşürdü.", 12
    ) | {"section_title": "Hedef bölüm"})
    plan["cases"][0]["discovery_section_filters"] = [{"section_title": "Hedef bölüm", "hard": True}]
    row = build(questions, corpus, plan)["proposals"][0]
    assert {item["section_title"] for item in row["suggestions"]} == {"Hedef bölüm"}
