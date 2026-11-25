import hashlib
import json

from app.pipeline.deepseek_crop_visual_review import _request, review


def _response(identifier, verdict="quote_not_visible"):
    return {"choices": [{"message": {"content": json.dumps({"id": identifier, "verdict": verdict,
        "quote_readable": True, "text_only": True, "reason": "Alıntı kırpımda görünmüyor."})}}]}


def test_reviews_only_material_mismatches_and_never_enables_runtime(tmp_path):
    context = tmp_path / "context-crops"
    context.mkdir()
    image = context / "one.png"
    image.write_bytes(b"png-placeholder")
    pack = {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64,
            "questions": [{"id": "one", "question": "Soru?", "choices": ["A", "B", "C", "D", "E"]},
                          {"id": "two", "question": "Soru 2?", "choices": ["A", "B", "C", "D", "E"]}]}
    queue = {"schema": "ayt-history-crop-repair-review-v1", "candidate_checksum": "a" * 64,
             "reviews": [{"id": "one", "priority": 1, "reason": "material_text_mismatch", "source_checksum": "b" * 64,
                          "page": 1, "context_crop": "context-crops/one.png", "candidate_quote": "Alıntı"},
                         {"id": "two", "priority": 2, "reason": "near_text_match", "source_checksum": "b" * 64,
                          "page": 1, "context_crop": "context-crops/one.png", "candidate_quote": "Alıntı"}]}
    result = review(queue, pack, tmp_path, "test-key", request_fn=lambda *_: _response("one"))
    assert result["summary"] == {"evaluated_count": 1, "verdicts": {"quote_not_visible": 1}}
    assert result["evaluations"][0]["context_crop_sha256"] == hashlib.sha256(image.read_bytes()).hexdigest()
    assert result["runtime_enabled"] is False
    assert result["is_human_teacher_approval"] is False


def test_rejects_invalid_model_reply(tmp_path):
    (tmp_path / "context-crops").mkdir()
    (tmp_path / "context-crops" / "one.png").write_bytes(b"png")
    pack = {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64,
            "questions": [{"id": "one", "question": "Soru?", "choices": ["A", "B", "C", "D", "E"]}]}
    queue = {"schema": "ayt-history-crop-repair-review-v1", "candidate_checksum": "a" * 64,
             "reviews": [{"id": "one", "priority": 1, "reason": "material_text_mismatch", "source_checksum": "b" * 64,
                          "page": 1, "context_crop": "context-crops/one.png", "candidate_quote": "Alıntı"}]}
    try:
        review(queue, pack, tmp_path, "test-key", request_fn=lambda *_: _response("wrong"))
    except ValueError as error:
        assert "fail-closed" in str(error)
    else:
        raise AssertionError("Geçersiz dış yanıt reddedilmeliydi")


def test_retries_only_an_empty_provider_completion(tmp_path):
    (tmp_path / "context-crops").mkdir()
    (tmp_path / "context-crops" / "one.png").write_bytes(b"png")
    pack = {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64,
            "questions": [{"id": "one", "question": "Soru?", "choices": ["A", "B", "C", "D", "E"]}]}
    queue = {"schema": "ayt-history-crop-repair-review-v1", "candidate_checksum": "a" * 64,
             "reviews": [{"id": "one", "priority": 1, "reason": "material_text_mismatch", "source_checksum": "b" * 64,
                          "page": 1, "context_crop": "context-crops/one.png", "candidate_quote": "Alıntı"}]}
    responses = iter([{"choices": [{"message": {"content": "", "reasoning_content": "kısa"}}]}, _response("one")])
    result = review(queue, pack, tmp_path, "test-key", request_fn=lambda *_: next(responses))
    assert result["evaluations"][0]["attempt_count"] == 2


def test_uses_non_thinking_bounded_json_mode_for_visual_classification(tmp_path):
    image = tmp_path / "crop.png"
    image.write_bytes(b"png")
    request = _request({"id": "one", "candidate_quote": "Alıntı", "page": 1},
                       {"question": "Soru?", "choices": ["A", "B", "C", "D", "E"]}, image, "deepseek-flash")
    assert request["thinking"] == {"type": "disabled"}
    assert request["max_tokens"] == 256
    assert request["response_format"] == {"type": "json_object"}
