import json

from app.pipeline.deepseek_source_relation_judge import build_request, direct_queue, judge


def _inputs():
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "corpus-v1", "books": [{"grade": 12, "source_name": "history.pdf", "source_checksum": "source-v1", "index": {"chunks": [{"id": "chunk-one", "page": 8, "bbox": [1, 2, 3, 4], "text": "Mustafa Kemal öğretmeni Mehmet Tevfik Bey'in etkisiyle tarihe ilgi duydu."}]}}]}
    fact = {"subject": "Mustafa Kemal", "subject_kind": "kisi", "relation": "iliskilidir", "object": "Mehmet Tevfik Bey", "object_kind": "kisi", "relation_phrase": "etkisiyle tarihe ilgi duydu", "quote_sha256": "quote", "review_status": "teacher_pdf_crop_required"}
    proposals = {"schema": "deepseek-source-relation-proposals-v1", "corpus_checksum": "corpus-v1", "sources": [{"source_checksum": "source-v1", "chunk_id": "chunk-one", "facts": [fact]}]}
    return proposals, corpus, fact


def test_second_pass_only_sends_source_and_proposed_relation():
    _, corpus, fact = _inputs()
    request = build_request({**corpus["books"][0]["index"]["chunks"][0], "source_checksum": "source-v1"}, fact, "deepseek-chat")
    text = request["messages"][0]["content"]
    assert "source_excerpt" in text and "proposed_relation" in text
    assert "answer_key" not in text


def test_direct_queue_remains_unapproved_after_second_pass():
    proposals, corpus, _ = _inputs()
    def fake_call(_request, _key, _timeout):
        return {"choices": [{"message": {"content": json.dumps({"verdict": "direct", "reason_code": "literal_relation", "requires_teacher_pdf_crop_review": True})}}]}
    decisions = judge(proposals, corpus, "secret", request_fn=fake_call)
    queue = direct_queue(proposals, decisions)
    assert decisions["is_teacher_approval"] is False
    assert queue["summary"]["proposed_relation_count"] == 1
    assert queue["sources"][0]["facts"][0]["review_status"] == "teacher_pdf_crop_required"
