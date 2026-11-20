from app.pipeline.deepseek_question_semantic_validation import validate


def pack():
    return {"schema": "ayt-history-original-question-candidate-pack-v1", "corpus_checksum": "c", "candidate_checksum": "d",
            "questions": [{"id": "authoring-001", "question": "Soru", "choices": ["a", "b", "c", "d", "e"], "correct_label": "B",
            "status": "source_crop_validation_required", "runtime_enabled": False, "source_evidence": {"quote": "Kaynak"}}]}


def test_accepts_only_matching_source_resolved_label():
    def fake(_request, _key, _timeout):
        return {"choices": [{"message": {"content": '{"validations":[{"id":"authoring-001","verdict":"accept_for_release_validation","source_resolved_label":"B","single_best_answer":true,"text_only":true,"directly_grounded":true,"reason":"doğrudan"}]}'}}]}
    result = validate(pack(), "secret", request_fn=fake)
    assert result["summary"]["verdicts"] == {"accept_for_release_validation": 1}
    assert result["runtime_enabled"] is False
