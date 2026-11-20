from app.pipeline.deepseek_relation_retrieval_review import review


def test_review_uses_only_question_and_source_cards_with_complete_json_labels():
    queue = {"schema": "ogm-ayt-relation-discovery-review-queue-v1", "source_checksum": "s", "corpus_checksum": "c",
             "proposals": [{"candidate_id": "q", "suggestions": [
                 {"source_checksum": "book", "chunk_id": "one", "text": "Kanıt bir."},
                 {"source_checksum": "book", "chunk_id": "two", "text": "Kanıt iki."},
             ]}]}
    calibration = {"source_checksum": "s", "corpus_checksum": "c", "queries": [{"id": "q", "query": "Soru"}]}
    def fake(_request, _key, _timeout):
        return {"choices": [{"message": {"content": '{"question_diagnosis":"direct_evidence_found","judgments":[{"source_key":"book:one","verdict":"support","diagnostic":"direct_support"},{"source_key":"book:two","verdict":"wrong","diagnostic":"irrelevant"}]}'}}]}
    result = review(queue, calibration, "secret", request_fn=fake)
    record = result["reviews"][0]
    assert record["source_text_checked"] is True
    assert record["crop_checked"] is False
    assert result["answer_key_accessed"] is False
