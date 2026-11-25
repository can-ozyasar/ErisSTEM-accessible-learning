import pytest

from app.pipeline.freeze_ogm_evidence_research_split import build


def _package(groups: int = 6, questions_per_group: int = 5):
    return {
        "schema": "ogm-ayt-history-source-grounded-pilot-candidates-v1",
        "source_checksum": "question-pdf-checksum",
        "runtime_enabled": False,
        "questions": [
            {"candidate_id": f"ogm:test:d{group}:p{page}:q{question}"}
            for group in range(1, groups + 1)
            for page, question in [(group, offset) for offset in range(1, questions_per_group + 1)]
        ],
    }


def test_freezes_deterministic_content_free_group_split():
    package = _package()
    result = build(package)

    assert result["question_count"] == 30
    assert sum(result["split_counts"].values()) == 30
    assert result["runtime_enabled"] is False
    assert result["qlora_enabled"] is False
    assert "question_text" not in result
    for group in range(1, 7):
        assigned = {result["splits"][f"ogm:test:d{group}:p{group}:q{question}"] for question in range(1, 6)}
        assert len(assigned) == 1
    assert build(package) == result


def test_refuses_runtime_enabled_or_too_small_input():
    package = _package()
    package["runtime_enabled"] = True
    with pytest.raises(ValueError, match="çalışma zamanına kapalı"):
        build(package)
    with pytest.raises(ValueError, match="en az 24"):
        build(_package(groups=2, questions_per_group=5))
