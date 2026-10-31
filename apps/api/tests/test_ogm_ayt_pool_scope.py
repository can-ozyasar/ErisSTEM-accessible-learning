import pytest

from app.pipeline.ogm_ayt_pool_scope import DEFAULT_TOPICS, build


def test_scope_keeps_only_test_pages_and_locks_six_units():
    pages = []
    for index, topic in enumerate(DEFAULT_TOPICS):
        pages.extend([
            {"page": index * 10 + 1, "topic": topic, "category": "test_candidate"},
            {"page": index * 10 + 2, "topic": topic, "category": "solved_or_explained"},
        ])
    result = build({"schema": "ogm-ayt-page-classification-v1", "source_checksum": "source-v1", "pages": pages})
    assert result["grade"] == 12
    assert result["page_count"] == 6
    assert result["page_allowlist"] == [1, 11, 21, 31, 41, 51]
    assert result["answer_key_accessed"] is False


def test_scope_requires_test_pages_for_every_unit():
    with pytest.raises(ValueError, match="Test sayfası"):
        build({"schema": "ogm-ayt-page-classification-v1", "source_checksum": "source-v1", "pages": []})
