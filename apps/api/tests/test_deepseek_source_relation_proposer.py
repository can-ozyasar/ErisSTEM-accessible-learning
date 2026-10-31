import json

from app.pipeline.deepseek_source_relation_proposer import build_request, propose


def _inputs():
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "corpus-v1", "books": [{
        "grade": 12, "source_name": "history.pdf", "source_checksum": "source-v1", "index": {"chunks": [{
            "id": "chunk-one", "page": 8, "bbox": [1, 2, 3, 4],
            "text": "Mustafa Kemal tarih öğretmeni Mehmet Tevfik Bey'in etkisiyle tarihe ilgi duydu.",
        }]},
    }]}
    proposals = {"schema": "ayt-evidence-bundle-proposals-v1", "corpus_checksum": "corpus-v1",
                 "proposals": [{"suggestions": [{"source_checksum": "source-v1", "chunk_id": "chunk-one",
                                                      "text": corpus["books"][0]["index"]["chunks"][0]["text"]}]}]}
    return proposals, corpus


def test_request_never_carries_question_or_answer_data():
    request = build_request(_inputs()[1]["books"][0]["index"]["chunks"][0], "deepseek-chat")
    text = request["messages"][0]["content"]
    assert "source_excerpt" in text
    assert "cevabı" in text
    assert "answer_key" not in text


def test_relation_proposals_are_locally_endpoint_and_quote_checked_then_remain_unapproved():
    proposals, corpus = _inputs()

    def fake_call(_request, _key, _timeout):
        return {"choices": [{"message": {"content": json.dumps({"facts": [{
            "subject": "Mustafa Kemal", "subject_kind": "kisi", "relation": "iliskilidir",
            "object": "Mehmet Tevfik Bey", "object_kind": "kisi",
            "relation_phrase": "etkisiyle tarihe ilgi duydu",
            "evidence_excerpt": "Mustafa Kemal tarih öğretmeni Mehmet Tevfik Bey'in etkisiyle tarihe ilgi duydu.",
        }, {"subject": "Uydurma", "subject_kind": "olay", "relation": "neden_oldu",
            "object": "Bilgi", "object_kind": "kavram", "relation_phrase": "yok", "evidence_excerpt": "yok"}]})}}]}

    result = propose(proposals, corpus, "secret", request_fn=fake_call)
    fact = result["sources"][0]["facts"][0]
    serialized = json.dumps(result, ensure_ascii=False)
    assert result["summary"]["proposed_relation_count"] == 1
    assert result["summary"]["rejected_relation_count"] == 1
    assert fact["review_status"] == "teacher_pdf_crop_required"
    assert result["is_teacher_approval"] is False
    assert "Mustafa Kemal tarih öğretmeni" not in serialized
    assert "secret" not in serialized


def test_relation_proposer_retries_invalid_json_without_persisting_the_raw_response():
    proposals, corpus = _inputs()
    calls = []

    def fake_call(_request, _key, _timeout):
        calls.append(1)
        content = "{" if len(calls) == 1 else json.dumps({"facts": []})
        return {"choices": [{"message": {"content": content}}]}

    result = propose(proposals, corpus, "secret", request_fn=fake_call)
    assert len(calls) == 2
    assert result["summary"]["invalid_json_retries"] == 1
    assert result["summary"]["invalid_json_final_failures"] == 0


def test_relation_proposer_rejects_clause_nodes_and_wrong_typed_relation_shape():
    proposals, corpus = _inputs()

    def fake_call(_request, _key, _timeout):
        return {"choices": [{"message": {"content": json.dumps({"facts": [{
            "subject": "Mustafa Kemal", "subject_kind": "olay", "relation": "gerceklesti_tarih",
            "object": "1896", "object_kind": "tarih_donem", "relation_phrase": "girdi",
            "evidence_excerpt": "Mustafa Kemal tarih öğretmeni Mehmet Tevfik Bey'in etkisiyle tarihe ilgi duydu.",
        }, {"subject": "Mustafa Kemal", "subject_kind": "kisi", "relation": "iliskilidir",
            "object": "tarihe ilgi duydu", "object_kind": "kavram", "relation_phrase": "ilgi duydu",
            "evidence_excerpt": "Mustafa Kemal tarih öğretmeni Mehmet Tevfik Bey'in etkisiyle tarihe ilgi duydu.",
        }]})}}]}

    result = propose(proposals, corpus, "secret", request_fn=fake_call)
    assert result["summary"]["proposed_relation_count"] == 0
    assert result["summary"]["rejected_relation_count"] == 2


def test_relation_proposer_rejects_passive_relation_that_can_reverse_direction():
    proposals, corpus = _inputs()

    def fake_call(_request, _key, _timeout):
        return {"choices": [{"message": {"content": json.dumps({"facts": [{
            "subject": "Mustafa Kemal", "subject_kind": "kisi", "relation": "iliskilidir",
            "object": "Mehmet Tevfik Bey", "object_kind": "kisi", "relation_phrase": "etkilendi",
            "evidence_excerpt": "Mustafa Kemal tarih öğretmeni Mehmet Tevfik Bey'in etkisiyle tarihe ilgi duydu.",
        }]})}}]}

    result = propose(proposals, corpus, "secret", request_fn=fake_call)
    assert result["summary"]["proposed_relation_count"] == 0
