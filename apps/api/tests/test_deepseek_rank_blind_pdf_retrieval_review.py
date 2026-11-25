import json

from app.pipeline.deepseek_rank_blind_pdf_retrieval_review import assemble, review


def _template(tmp_path):
    crops = tmp_path / "crops"
    crops.mkdir()
    rows = []
    for number in range(24):
        cards = []
        for card in range(3):
            filename = f"{number}-{card}.png"
            (crops / filename).write_bytes(b"png")
            cards.append({"source_key": f"source:{number}-{card}", "source_checksum": "source", "atom_id": f"{number}-{card}",
                          "page": 1, "bbox": [1, 2, 3, 4], "crop": f"crops/{filename}", "excerpt": f"Kanıt {number}-{card}",
                          "decision": None, "rationale": ""})
        rows.append({"id": f"q-{number}", "question": "Soru", "choices": ["A", "B", "C", "D", "E"], "cards": cards,
                     "case_decision": None, "reviewer": None, "reviewed_at": None, "notes": ""})
    return {"schema": "ayt-history-rank-blind-pdf-retrieval-review-template-v1", "candidate_checksum": "a",
            "corpus_checksum": "b", "split_checksum": "c", "source_catalog_checksum": "d", "reviews": rows,
            "answer_key_accessed": False, "worked_explanation_accessed": False, "reference_atom_accessed": False,
            "runtime_enabled": False, "qlora_enabled": False}


def _response():
    return {"choices": [{"message": {"content": json.dumps({"cards": [
        {"card": 1, "decision": "relevant", "rationale": "PDF kesiti sorunun ayırt edici tarihsel ilişkisini açıkça ifade etmektedir."},
        {"card": 2, "decision": "wrong", "rationale": "PDF kesiti sorudaki olay veya ilişkiyle ilgili somut bilgi içermemektedir."},
        {"card": 3, "decision": "insufficient", "rationale": "PDF kesiti aynı konuyu anmaktadır ancak seçenekleri ayırmaya tek başına yetmez."}],
        "case_decision": "sufficient", "notes": "PDF kesitiyle sınırlandırılmış ajan değerlendirmesi."}, ensure_ascii=False)}}]}


def test_reviews_answer_blind_pdf_cards_and_assembles_a_nonhuman_completed_manifest(tmp_path):
    template = _template(tmp_path)
    part = review(template, tmp_path, "test-key", limit=8, request_fn=lambda *_: _response())
    assert len(part["reviews"]) == 8
    assert part["answer_key_accessed"] is False
    assert part["is_human_teacher_approval"] is False
    parts = [review(template, tmp_path, "test-key", offset=offset, limit=8, request_fn=lambda *_: _response()) for offset in (0, 8, 16)]
    completed, audit = assemble(template, parts)
    assert completed["reviews"][0]["reviewer"] == "deepseek_history_teacher_agent_v1"
    assert completed["is_human_teacher_approval"] is False
    assert len(audit["records"]) == 24


def test_rejects_card_coverage_failure(tmp_path):
    template = _template(tmp_path)
    broken = _response()
    broken["choices"][0]["message"]["content"] = json.dumps({"cards": [], "case_decision": "insufficient", "notes": "Yetersiz kart listesi."})
    try:
        review(template, tmp_path, "test-key", limit=1, request_fn=lambda *_: broken)
    except ValueError as error:
        assert "her PDF kartını" in str(error)
    else:
        raise AssertionError("Eksik kart değerlendirmesi reddedilmeliydi")
