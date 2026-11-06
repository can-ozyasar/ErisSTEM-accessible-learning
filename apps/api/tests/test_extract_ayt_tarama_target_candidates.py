import pytest

from app.pipeline.extract_ayt_tarama_target_candidates import build


def test_rejects_non_target_test(tmp_path):
    source = tmp_path / "empty.pdf"
    source.write_bytes(b"not a pdf")
    with pytest.raises(ValueError):
        build(source, tests={22})
