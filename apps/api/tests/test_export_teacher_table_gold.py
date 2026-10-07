from app.job_store import TableReviewStore, make_session_factory
from app.pipeline.export_teacher_table_gold import teacher_approved_gold


def _payload(identifier: str, region: str) -> dict:
    return {
        "id": identifier, "document_id": "source-a", "schema_version": "visual-table-draft-v1", "kind": "table",
        "source": {"region_id": region, "source_checksum": "a" * 64, "page": 1, "bbox": [1, 2, 30, 40]},
        "cells": [{"row": 1, "column": 1, "role": "header", "text": "Başlık", "confidence": 0.0}],
        "confidence": 0.0, "publication_status": "requires-gold-and-teacher-review",
        "candidate_status": "candidate-vector-native-needs-gold-and-review",
    }


def test_gold_export_blocks_without_three_teacher_approved_tables(tmp_path):
    tables = TableReviewStore(make_session_factory(f"sqlite:///{tmp_path / 'reviews.db'}"))
    for index in range(2):
        payload = _payload(f"table-{index}", f"region-{index}")
        tables.create(payload)
        tables.save(payload["id"], payload, status="approved", revision=2)

    manifest, report = teacher_approved_gold(tables)

    assert report["status"] == "blocked_insufficient_teacher_approved_tables"
    assert report["contains_document_content"] is False
    assert len(manifest["tables"]) == 2


def test_gold_export_is_ready_with_three_teacher_approved_tables(tmp_path):
    tables = TableReviewStore(make_session_factory(f"sqlite:///{tmp_path / 'reviews.db'}"))
    for index in range(3):
        payload = _payload(f"table-{index}", f"region-{index}")
        tables.create(payload)
        tables.save(payload["id"], payload, status="approved", revision=2)

    manifest, report = teacher_approved_gold(tables)

    assert report["status"] == "ready"
    assert len(manifest["tables"]) == 3
