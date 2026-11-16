"""The AYT graph audit must stay inside the selected source version."""

import pytest

from app.pipeline.audit_autonomous_graph_scope import audit


def _payloads() -> tuple[dict, dict]:
    checksum = "a" * 64
    return (
        {"schema": "ayt-history-knowledge-graph-v1", "corpus_checksum": checksum,
         "nodes": [], "edges": []},
        {"grade": 12, "target_question_count": 120,
         "source_binding": {"corpus_checksum": checksum, "meb_source_checksum": "b" * 64},
         "sections": [{"section_id": "2.1", "book_page_range": {"start": 10, "end": 20}}]},
    )


def test_audit_keeps_training_gate_closed_without_reviewed_questions():
    graph, scope = _payloads()
    result = audit(graph, scope)
    assert result["generated_candidate_count"] == 0
    assert result["production_ready_count"] == 0
    assert result["qlora_enabled"] is False


def test_audit_rejects_stale_scope_checksum():
    graph, scope = _payloads()
    scope["source_binding"]["corpus_checksum"] = "c" * 64
    with pytest.raises(ValueError, match="checksum"):
        audit(graph, scope)
