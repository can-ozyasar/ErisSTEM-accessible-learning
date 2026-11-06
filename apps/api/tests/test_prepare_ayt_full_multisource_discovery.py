import json
from pathlib import Path

import pytest

from app.pipeline.prepare_ayt_full_multisource_discovery import build

ROOT = Path(__file__).parents[3]


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_prepares_four_source_answer_free_coverage_input():
    result = build(
        _load("data/private/yks-ayt-source-v1/official-ayt-multisource-dense-discovery-local11-12-v1.json"),
        _load("data/private/yks-ayt-source-v1/multi-history-rag-with-ayt-summary-atoms-v3.json"),
    )
    assert result["schema"] == "ayt-full-multisource-dense-discovery-v1"
    assert len(result["queries"]) == 10
    assert {item["grade"] for item in result["source_bindings"]} == {10, 11, 12}
    assert len(result["documents"]) > 4000
    assert all(result[key] is False for key in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"))


def test_rejects_answer_key_tainted_query_input():
    queries = _load("data/private/yks-ayt-source-v1/official-ayt-multisource-dense-discovery-local11-12-v1.json")
    queries["answer_key_accessed"] = True
    with pytest.raises(ValueError, match="erişimli"):
        build(queries, _load("data/private/yks-ayt-source-v1/multi-history-rag-with-ayt-summary-atoms-v3.json"))
