import json

from app.pipeline.review_final_bundle_answer import review


def test_answer_is_solved_blind_and_compared_locally():
    queue = {"schema": "ogm-ayt-real-question-evidence-queue-v1", "runtime_enabled": False,
             "question_source_checksum": "q", "proposals": [{"candidate_id": "id", "question_text": "Soru A) Bir B) İki",
             "suggestions": [{"id": "e", "excerpt": "Kaynak"}]}]}
    candidates = {"source_checksum": "q", "questions": [{"candidate_id": "id", "correct_choice": "B"}]}
    def fake(request, _key, _timeout):
        text = request["messages"][0]["content"]
        assert "correct_choice" not in text
        assert "claimed_correct_label" not in text
        return {"choices": [{"message": {"content": json.dumps({"label": "B", "reason": "Kaynak"})}}]}
    result = review(queue, candidates, "fake", request_fn=fake)
    assert result["reviews"][0]["matches_answer_key"] is True
    assert result["model_received_answer_key"] is False
    assert result["runtime_enabled"] is False
