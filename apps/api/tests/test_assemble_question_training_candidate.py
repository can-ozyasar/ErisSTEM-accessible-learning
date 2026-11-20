from app.pipeline.assemble_question_training_candidate import build


def pack(checksum: str, identifier: str = "a"):
    return {"schema": "ayt-history-original-question-candidate-pack-v1", "corpus_checksum": "c", "candidate_checksum": checksum,
            "questions": [{"id": identifier, "question": "S", "spoken_question": "S", "choices": ["a"] * 5, "correct_label": "A", "explanation": "E",
            "source_evidence": {"quote": "K"}, "status": "source_crop_validation_required", "runtime_enabled": False}]}


def validation(checksum: str, identifier: str = "a"):
    return {"schema": "deepseek-question-semantic-validation-v1", "corpus_checksum": "c", "candidate_checksum": checksum,
            "validations": [{"id": identifier, "verdict": "accept_for_release_validation"}]}


def test_accepts_unchanged_prior_semantic_validation():
    result = build(pack("new"), pack("old"), [validation("old")])
    assert result["question_bank_training_candidate_ready"] is True
    assert result["qlora_training_ready"] is False
