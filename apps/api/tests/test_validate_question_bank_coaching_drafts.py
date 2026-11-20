from app.pipeline.validate_question_bank_coaching_drafts import validate


def payload():
    turns = [{"case": case, "guide_response": "Kaynağı hangi sözle karşılaştırırsın?", "source_ids": ["s"], "evidence_quotes": ["k"], "early_answer_disclosed": False, "runtime_enabled": False}
             for case in ("soruyu_anlama", "hatirlayani_ortaya_cikar", "kanitla_bag_kur", "siki_sina", "yanlis_cevabi_duzelt", "dogruyu_pekistir")]
    return {"schema": "ayt-history-source-bound-coaching-drafts-v1", "corpus_checksum": "c", "question_bank_checksum": "q",
            "records": [{"question_id": f"q-{i}", "turns": turns} for i in range(120)]}


def test_accepts_complete_source_bound_single_question_drafts():
    result = validate(payload())
    assert result["accepted"] is True
    assert result["turns_checked"] == 720


def test_rejects_early_answer_leakage():
    value = payload()
    value["records"][0]["turns"][0] = {**value["records"][0]["turns"][0], "guide_response": "Doğru cevap A şıkkı mı?"}
    assert validate(value)["accepted"] is False
