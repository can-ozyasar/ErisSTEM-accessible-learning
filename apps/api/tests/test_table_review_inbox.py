from app.pipeline.table_review_inbox import to_review_inbox


def test_only_vector_native_candidates_become_teacher_review_envelopes():
    checksum = "a" * 64
    results = [
        {
            "status": "candidate-vector-native-needs-gold-and-review",
            "draft": {
                "schema_version": "visual-table-draft-v1", "kind": "table",
                "source": {"region_id": "p46-table", "source_checksum": checksum, "page": 46, "bbox": [1, 2, 30, 40]},
                "cells": [{"row": 1, "column": 1, "role": "header", "text": "Başlık", "confidence": 0.0}],
                "confidence": 0.0, "publication_status": "requires-gold-and-teacher-review",
            },
        },
        {"status": "blocked-insufficient-vector-grid", "draft": None},
    ]

    inbox = to_review_inbox(results, "source-a")

    assert len(inbox) == 1
    assert inbox[0]["id"] == f"vector-native-{checksum[:16]}-p46-table"
    assert inbox[0]["candidate_status"] == "candidate-vector-native-needs-gold-and-review"
