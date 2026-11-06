import json
from pathlib import Path

from app.pipeline.prepare_ayt_target_root_dense_discovery import build

ROOT = Path(__file__).parents[3]


def _load(name: str) -> dict:
    return json.loads((ROOT / "data/private/yks-ayt-source-v1" / name).read_text(encoding="utf-8"))


def test_prepares_root_only_answer_free_queries():
    result = build(_load("official-ayt-target-discovery-pool-local12-v1.json"), _load("multi-history-rag-target12-local-v1.json"))
    assert result["schema"] == "ayt-target-root-dense-discovery-v1"
    assert result["query_policy"] == "question_root_and_need_plan_only"
    assert len(result["queries"]) == 10
    assert result["answer_key_accessed"] is False
    assert result["runtime_enabled"] is False
