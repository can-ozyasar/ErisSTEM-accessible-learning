import pytest
from app.pipeline.validate_meb12_assessment_13_audit import validate


def test_rejects_wrong_schema():
    with pytest.raises(ValueError): validate({"schema": "wrong"})
