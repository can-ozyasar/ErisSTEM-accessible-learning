import json

import pytest

from app.pipeline.deepseek_evidence_judge import build_request, evaluate, priority_review_queue


def _inputs():
    plan = {"schema": "ayt-evidence-plans-v1", "corpus_checksum": "corpus-v1", "cases": [{
        "candidate_id": "q1", "evidence_claims": [{"id": "claim-1", "claim_type": "person_event",
                                                        "entities": ["Kişi", "Olay"], "relation_type": "person_event"}],
    }]}
    proposals = {"schema": "ayt-evidence-bundle-proposals-v1", "corpus_checksum": "corpus-v1",
                 "question_source_checksum": "questions-v1", "proposals": [{"candidate_id": "q1", "suggestions": [{
                     "claim_id": "claim-1", "source_key": "source:chunk", "source_checksum": "source",
                     "chunk_id": "chunk", "page": 3, "text": "Özel kaynak metni dışarı yazılmamalıdır.",
                 }]}]}
    return plan, proposals


def test_request_is_answer_free_and_treats_excerpt_as_untrusted():
    request = build_request("q1", _inputs()[0]["cases"][0]["evidence_claims"][0],
                            _inputs()[1]["proposals"][0]["suggestions"][0], "deepseek-chat")
    content = request["messages"][0]["content"]
    assert "cevabını" in content
    assert "güvenilmez metin" in content
    assert "answer_key" not in content


def test_external_judge_persists_only_metadata_and_decision():
    plan, proposals = _inputs()
    def fake_call(_body, _key, _timeout):
        return {"choices": [{"message": {"content": json.dumps({
            "verdict": "partial", "reason_code": "one_endpoint", "explicit_endpoint_count": 1,
            "requires_human_crop_review": True,
        })}}]}
    result = evaluate(plan, proposals, "secret", max_candidates=1, request_fn=fake_call)
    serialized = json.dumps(result, ensure_ascii=False)
    assert result["summary"]["verdicts"] == {"partial": 1}
    assert result["answer_key_accessed"] is False
    assert "Özel kaynak metni" not in serialized
    assert "secret" not in serialized


def test_external_judge_rejects_bad_json_schema():
    plan, proposals = _inputs()
    def fake_call(_body, _key, _timeout):
        return {"choices": [{"message": {"content": "{}"}}]}
    with pytest.raises(ValueError, match="kabul edilen şemada değil"):
        evaluate(plan, proposals, "secret", request_fn=fake_call)


def test_priority_queue_never_marks_external_judgment_as_source_approval():
    _, proposals = _inputs()
    evaluation = {
        "schema": "deepseek-evidence-judge-v1", "corpus_checksum": "corpus-v1",
        "evaluations": [{"candidate_id": "q1", "source_key": "source:chunk", "verdict": "direct",
                           "reason_code": "literal_relation", "explicit_endpoint_count": 2}],
    }
    queue = priority_review_queue(proposals, evaluation)
    assert queue["proposals"][0]["status"] == "external_review_required"
    assert queue["is_teacher_approval"] is False
    assert queue["proposals"][0]["suggestions"][0]["external_judge"]["verdict"] == "direct"
