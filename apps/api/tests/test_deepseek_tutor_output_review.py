from app.pipeline.deepseek_tutor_output_review import review


def pack():
    return {"schema": "eristem-qlora-synthetic-behavior-review-pack-v1", "candidate": "adapter",
            "source_report_sha256": "a" * 64, "records": [{"id": "synthetic-01", "case": "soruyu_anlama",
            "question": "Soru", "evidence": "Kanıt", "evidence_available": True, "response": "Kanıttaki ipucu ne?"}]}


def test_review_requires_one_well_formed_label_per_record():
    def fake(*_):
        return {"choices": [{"message": {"content": '{"reviews":[{"id":"synthetic-01","source_external_claim":false,"wrong_source_attribution":false,"natural_turkish":true,"pedagogically_useful":true,"reason":"uygun"}]}'}}]}
    result = review(pack(), "secret", request_fn=fake)
    assert result["reviews"][0]["source_external_claim"] is False
    assert result["is_human_teacher_approval"] is False


def test_review_retries_one_transient_transport_failure():
    calls = 0
    def fake(*_):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary network")
        return {"choices": [{"message": {"content": '{"reviews":[{"id":"synthetic-01","source_external_claim":false,"wrong_source_attribution":false,"natural_turkish":true,"pedagogically_useful":true,"reason":"uygun"}]}'}}]}
    result = review(pack(), "secret", request_fn=fake)
    assert result["transport_attempts"] == 2
