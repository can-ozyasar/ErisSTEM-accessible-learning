import pytest

from app.pipeline.ayt_evidence_plan_patch import apply


def _plan():
    return {"schema": "ayt-evidence-plans-priority-agent-draft-v1", "plans": [{
        "candidate_id": "q1", "evidence_claims": [
            {"id": "c1", "entities": ["Mora İsyanı"], "search_terms": ["Mora"]},
            {"id": "c2", "entities": ["Kavalalı"], "search_terms": ["Kavalalı"]},
        ], "support_requirements": {"all_must_support_claim_ids": ["c1", "c2"]},
    }]}


def _patches():
    return {"schema": "ayt-evidence-plan-patches-agent-draft-v1", "is_teacher_approval": False,
            "answer_key_accessed": False, "patches": [{"candidate_id": "q1", "operations": [{
                "op": "replace_claim_match", "claim_id": "c1",
                "all_of": [["Mora", "Rum İsyanı"]], "any_of": [["Yunanistan"]],
            }]}]}


def test_patch_creates_private_nonapproval_plan_with_alias_groups():
    result = apply(_plan(), _patches())
    claim = result["cases"][0]["evidence_claims"][0]
    assert result["schema"] == "ayt-evidence-plans-v1"
    assert result["is_teacher_approval"] is False
    assert claim["all_of_groups"] == [["Mora", "Rum İsyanı"]]
    assert claim["any_of_groups"] == [["Yunanistan"]]


def test_patch_cannot_claim_teacher_approval_or_unknown_question():
    patches = _patches()
    patches["is_teacher_approval"] = True
    with pytest.raises(ValueError, match="cevap anahtarı"):
        apply(_plan(), patches)
    patches = _patches()
    patches["patches"][0]["candidate_id"] = "wrong"
    with pytest.raises(ValueError, match="bilinmeyen soruya"):
        apply(_plan(), patches)


def test_patch_splits_required_claim_and_updates_discriminator_references():
    patches = _patches()
    patches["patches"][0]["operations"] = [{
        "op": "split_claim", "claim_id": "c1", "into": [
            {"id": "c1a", "role": "relation", "all_of": [["Mora"]]},
            {"id": "c1b", "role": "relation", "all_of": [["Rum"]]},
        ],
    }]
    plan = _plan()
    plan["plans"][0]["option_discriminators"] = [{"id": "d1", "claim_ids": ["c1"]}]
    result = apply(plan, patches)
    case = result["cases"][0]
    assert case["support_requirements"]["all_must_support_claim_ids"] == ["c1a", "c1b", "c2"]
    assert case["option_discriminators"][0]["claim_ids"] == ["c1a", "c1b"]
