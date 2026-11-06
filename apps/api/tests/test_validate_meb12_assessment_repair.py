import pytest

from app.pipeline.validate_meb12_assessment_repair import validate


def test_rejects_answer_access():
    with pytest.raises(ValueError):
        validate({"schema": "ayt-target-question-candidates-v1", "answer_key_accessed": True})
