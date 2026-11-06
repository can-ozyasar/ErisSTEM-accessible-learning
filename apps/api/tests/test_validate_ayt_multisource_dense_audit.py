import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.pipeline.prepare_ayt_multisource_dense_review import build as prepare
from app.pipeline.validate_ayt_multisource_dense_audit import build

ROOT = Path(__file__).parents[3]


def _queue() -> dict:
    discovery = json.loads(
        (ROOT / "data/private/yks-ayt-source-v1/official-ayt-multisource-dense-discovery-local11-12-v1.json").read_text(encoding="utf-8")
    )
    ids = [row["id"] for row in discovery["documents"]]
    rankings = {
        "schema": "official-ayt-multisource-dense-discovery-rankings-v1",
        "corpus_checksum": discovery["corpus_checksum"],
        "source_bindings": discovery["source_bindings"],
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "rankings": {q["id"]: {"qwen_dense_tr": ids[:20], "bm25": ids[1:21], "rrf": ids[2:22]} for q in discovery["queries"]},
    }
    return prepare(discovery, rankings)


def _audit(queue: dict) -> dict:
    records = []
    for index, row in enumerate(queue["rows"]):
        cards = row["suggestions"]
        support = cards[0] if index == 0 else None
        records.append(
            {
                "candidate_id": row["candidate_id"],
                "decision": "direct" if support else "insufficient",
                "failure_diagnosis": "none" if support else "retrieval_miss",
                "reviewer_kind": "history_teacher_agent_v1",
                "is_human_teacher_approval": False,
                "pdf_crop_checked": True,
                "answer_key_accessed": False,
                "worked_explanation_accessed": False,
                "runtime_enabled": False,
                "qlora_enabled": False,
                "supporting_record_ids": [support["record_id"]] if support else [],
                "reviewed_suggestions": [
                    {"source_key": card["source_key"], "support": card is support, "pdf_crop_checked": True}
                    for card in cards
                ],
                "relation_edges": [
                    {"source_key": support["source_key"], "quote": support["excerpt"][:15]}
                ] if support else [],
            }
        )
    return {
        "schema": "teacher-official-ayt-multisource-dense-audit-v1",
        "input": {"queue_schema": queue["schema"], "corpus_checksum": queue["corpus_checksum"], "source_bindings": queue["source_bindings"]},
        "reviewer_kind": "history_teacher_agent_v1",
        "is_human_teacher_approval": False,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "records": records,
    }


def test_validates_completed_multisource_pdf_crop_audit():
    queue = _queue()
    result = build(queue, _audit(queue))
    assert result["question_count"] == 10
    assert result["supported_question_count"] == 1
    assert result["checked_card_count"] >= 30


def test_rejects_quote_outside_candidate_crop():
    queue = _queue()
    audit = _audit(queue)
    audit["records"][0]["relation_edges"][0]["quote"] = "kaynakta olmayan ifade"
    with pytest.raises(ValueError, match="birebir"):
        build(queue, audit)


def test_accepts_targeted_expansion_queue_schema():
    queue = deepcopy(_queue())
    queue["schema"] = "official-ayt-full-targeted-expansion-review-queue-v1"
    audit = _audit(queue)
    result = build(queue, audit)
    assert result["question_count"] == 10
