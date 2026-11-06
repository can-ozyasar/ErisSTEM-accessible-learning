import json
from pathlib import Path

import pytest

from app.pipeline.validate_ayt_relation_bundle_audit import build

ROOT = Path(__file__).parents[3]


def _load(path: str) -> dict:
    return json.loads((ROOT / "data/private/yks-ayt-source-v1" / path).read_text(encoding="utf-8"))


def test_validates_completed_relation_bundle_audit():
    result = build(
        _load("official-ayt-target-relation-bundle-review-queue-local12-v1.json"),
        _load("teacher-official-ayt-relation-bundle-audit-local12-v1.json"),
    )
    assert result["question_count"] == 10
    assert result["supported_question_count"] == 3
    assert result["relation_edge_count"] == 9


def test_rejects_edge_without_verbatim_crop_quote():
    queue = _load("official-ayt-target-relation-bundle-review-queue-local12-v1.json")
    audit = _load("teacher-official-ayt-relation-bundle-audit-local12-v1.json")
    audit["records"][0]["relation_edges"][0]["quote"] = "kaynakta olmayan ifade"
    with pytest.raises(ValueError, match="birebir"):
        build(queue, audit)
