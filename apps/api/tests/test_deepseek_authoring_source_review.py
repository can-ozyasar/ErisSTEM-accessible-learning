from app.pipeline.deepseek_authoring_source_review import review


def queue():
    return {"schema": "ayt-history-original-authoring-queue-v1", "corpus_checksum": "c", "queue_checksum": "q" * 64, "cards": [
        {"id": "authoring-001", "question_text": None, "choices": None, "correct_label": None,
         "source_evidence": {"quote": "Doğrudan tarihsel kanıt."}},
        {"id": "authoring-002", "question_text": None, "choices": None, "correct_label": None,
         "source_evidence": {"quote": "Bağlam gerektiren kısa kanıt."}},
    ]}


def test_reviews_source_only_cards_with_complete_labels():
    def fake(_request, _key, _timeout):
        return {"choices": [{"message": {"content": '{"reviews":[{"id":"authoring-001","verdict":"direct_fact","text_only_candidate":true},{"id":"authoring-002","verdict":"context_only","text_only_candidate":false}]}'}}]}
    result = review(queue(), "secret", request_fn=fake)
    assert result["summary"]["review_count"] == 2
    assert result["queue_checksum"] == "q" * 64
    assert result["answer_key_accessed"] is False
    assert result["is_human_teacher_approval"] is False
