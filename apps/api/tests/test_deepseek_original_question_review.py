from app.pipeline.deepseek_original_question_review import review


def drafts():
    return {"schema": "deepseek-original-question-drafts-v1", "corpus_checksum": "c", "queue_checksum": "q" * 64,
            "draft_offset": 0, "drafts": [{"id": "authoring-001", "question": "Soru?", "choices": ["a", "b", "c", "d", "e"],
            "correct_label": "B", "explanation": "Açıklama.", "source_evidence": {"quote": "Kaynak."}, "runtime_enabled": False}]}


def test_accepts_only_complete_fail_closed_review():
    def fake(_request, _key, _timeout):
        return {"choices": [{"message": {"content": '{"reviews":[{"id":"authoring-001","verdict":"accept_for_source_validation","source_support_direct":true,"single_best_answer":true,"text_only":true,"explanation_grounded":true,"reason":"doğrudan"}]}'}}]}
    result = review(drafts(), "secret", request_fn=fake)
    assert result["summary"]["verdicts"] == {"accept_for_source_validation": 1}
    assert result["runtime_enabled"] is False
