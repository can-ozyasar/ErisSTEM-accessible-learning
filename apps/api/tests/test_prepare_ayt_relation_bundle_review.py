import json
from pathlib import Path

import pytest

from app.pipeline.prepare_ayt_relation_bundle_review import build


def _load(name: str) -> dict:
    root = Path(__file__).parents[3]
    return json.loads((root / "data/private/yks-ayt-source-v1" / name).read_text(encoding="utf-8"))


def _rankings() -> dict:
    root = Path(__file__).parents[3]
    return json.loads((root / "data/private/kaggle-notebook-outputs/eristem-ayt-target-dense-discovery-local12-v2" / "official-ayt-target-dense-discovery-rankings-v1.json").read_text(encoding="utf-8"))


def test_builds_private_diverse_relation_review_queue():
    result = build(
        _load("official-ayt-target-dense-discovery-local12-v1.json"),
        _rankings(),
        _load("teacher-official-ayt-dense-audit-local12-v1.json"),
    )
    assert result["schema"] == "official-ayt-target-relation-bundle-review-queue-v1"
    assert len(result["rows"]) == 10
    assert result["runtime_enabled"] is False
    assert result["qlora_enabled"] is False
    assert result["answer_key_accessed"] is False
    assert all(3 <= len(row["suggestions"]) <= 10 for row in result["rows"])
    assert all(
        len({(card["source_checksum"], card["page"], tuple(card["bbox"])) for card in row["suggestions"]})
        == len(row["suggestions"])
        for row in result["rows"]
    )


def test_rejects_answer_key_tainted_input():
    discovery = _load("official-ayt-target-dense-discovery-local12-v1.json")
    discovery["answer_key_accessed"] = True
    with pytest.raises(ValueError, match="Cevap anahtarı"):
        build(discovery, _rankings(), _load("teacher-official-ayt-dense-audit-local12-v1.json"))
