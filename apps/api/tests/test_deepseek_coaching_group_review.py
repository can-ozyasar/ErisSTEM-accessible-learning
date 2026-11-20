from app.pipeline.deepseek_coaching_group_review import review


def payload():
    turn = {"case": "soruyu_anlama", "learner_state": "Karıştı.", "strategy": "focus_question", "guide_response": "Kökteki ipucu hangisi?", "evidence_quotes": ["Kaynak."]}
    return {"schema": "ayt-history-source-bound-coaching-drafts-v1", "corpus_checksum": "c", "question_bank_checksum": "q", "records": [{"question_id": "q1", "error_type": "genel", "turns": [turn] * 6}]}


def test_accepts_complete_group_review():
    def fake(*_): return {"choices": [{"message": {"content": '{"reviews":[{"question_id":"q1","verdict":"accept_for_qlora_candidate","source_grounded":true,"natural_turkish":true,"adaptive_scaffold":true,"no_early_answer_leakage":true,"reason":"uygun"}]}'}}]}
    assert review(payload(), "secret", request_fn=fake)["summary"]["review_count"] == 1
