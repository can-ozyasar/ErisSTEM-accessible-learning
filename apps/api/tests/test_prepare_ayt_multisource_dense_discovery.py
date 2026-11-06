import json
from pathlib import Path

from app.pipeline.prepare_ayt_multisource_dense_discovery import build

ROOT = Path(__file__).parents[3]


def load(name: str) -> dict:
    return json.loads((ROOT / 'data/private/yks-ayt-source-v1' / name).read_text())


def test_multisource_is_answer_free_and_has_two_bound_sources():
    result = build(load('official-ayt-target-discovery-pool-local12-v1.json'), load('multi-history-rag-local11-12-v1.json'))
    assert len(result['queries']) == 10 and len(result['documents']) > 2000
    assert {item['grade'] for item in result['source_bindings']} == {11, 12}
    assert result['answer_key_accessed'] is False and result['runtime_enabled'] is False
