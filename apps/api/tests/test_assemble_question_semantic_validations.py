import pytest

from app.pipeline.assemble_question_semantic_validations import build


def _pack():
    return {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "c" * 64,
            "corpus_checksum": "d" * 64,
            "questions": [{"id": f"q-{index:03d}"} for index in range(120)]}


def _batch(rows):
    return {"schema": "deepseek-question-semantic-validation-v1", "candidate_checksum": "c" * 64,
            "corpus_checksum": "d" * 64, "validations": rows,
            "answer_key_accessed": False, "student_data_accessed": False,
            "is_human_teacher_approval": False, "runtime_enabled": False, "qlora_enabled": False}


def _rows(start, end, verdict="accept_for_release_validation"):
    return [{"id": f"q-{index:03d}", "verdict": verdict, "runtime_enabled": False} for index in range(start, end)]


def test_seals_complete_batches_but_keeps_runtime_closed():
    result = build(_pack(), [_batch(_rows(0, 60)), _batch(_rows(60, 120, "reject"))])
    assert result["summary"] == {"candidate_count": 120, "ai_accepted": 60, "review_required": 60}
    assert result["runtime_enabled"] is False
    assert result["is_human_teacher_approval"] is False


def test_rejects_incomplete_or_duplicate_batches():
    with pytest.raises(ValueError, match="tamamını"):
        build(_pack(), [_batch(_rows(0, 119))])
    with pytest.raises(ValueError, match="yinelenen"):
        build(_pack(), [_batch(_rows(0, 120)), _batch(_rows(0, 1))])
