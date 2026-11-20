from app.pipeline.build_question_bank_coaching_drafts import build


def pack():
    question = {"id": "authoring-001", "question": "Bu olayın nedeni hangisidir?", "source_evidence": {"quote": "Kaynak olayın nedenini açıklar.", "source_checksum": "c", "atom_id": "a"}}
    return {"schema": "ayt-history-question-bank-training-candidate-v1", "question_bank_training_candidate_ready": True,
            "corpus_checksum": "c", "frozen_checksum": "f", "questions": [question] * 120}


def test_builds_six_source_bound_answer_safe_turns_per_question():
    result = build(pack())
    assert result["summary"]["draft_turns"] == 720
    assert len(result["records"][0]["turns"]) == 6
    assert all(turn["guide_response"].endswith("?") for turn in result["records"][0]["turns"])
    assert result["runtime_enabled"] is False
