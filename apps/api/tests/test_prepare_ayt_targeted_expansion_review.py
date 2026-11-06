import json
from pathlib import Path

from app.pipeline.prepare_ayt_targeted_expansion_review import build

ROOT = Path(__file__).parents[3]


def test_builds_expansion_for_only_unsupported_questions():
    discovery = json.loads((ROOT / "data/private/yks-ayt-source-v1/official-ayt-full-multisource-dense-discovery-local10-12-summary-v1.json").read_text(encoding="utf-8"))
    queue = json.loads((ROOT / "data/private/yks-ayt-source-v1/official-ayt-full-multisource-dense-review-queue-v1.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "data/private/yks-ayt-source-v1/teacher-official-ayt-full-multisource-dense-audit-v1.json").read_text(encoding="utf-8"))
    result = build(discovery, queue, audit, first_stage_limit=20, review_limit=3)
    assert result["schema"] == "official-ayt-full-targeted-expansion-review-queue-v1"
    assert len(result["rows"]) == 6
    assert all(len(row["suggestions"]) <= 3 for row in result["rows"])
    assert result["runtime_enabled"] is False
