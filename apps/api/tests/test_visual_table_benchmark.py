from app.pipeline.visual_result_schema import VisualTableDraft
from app.pipeline.visual_table_benchmark import (
    VisualTableGold,
    VisualTableGoldManifest,
    evaluate_manifest,
    evaluate_table,
)


def source() -> dict:
    return {"region_id": "table-p46-1", "source_checksum": "a" * 64, "page": 46, "bbox": [1, 2, 30, 40]}


def gold() -> VisualTableGold:
    return VisualTableGold.model_validate(
        {
            "schema_version": "visual-table-gold-v1",
            "kind": "table",
            "source": source(),
            "cells": [
                {"row": 1, "column": 1, "role": "header", "text": "Başlık"},
                {"row": 2, "column": 1, "role": "data", "text": "Değer"},
            ],
        }
    )


def candidate() -> VisualTableDraft:
    return VisualTableDraft.model_validate(
        {
            "kind": "table",
            "source": source(),
            "cells": [
                {"row": 1, "column": 1, "role": "header", "text": "Başlık", "confidence": 0},
                {"row": 2, "column": 1, "role": "data", "text": "Değer", "confidence": 0},
            ],
            "confidence": 0,
        }
    )


def test_exact_candidate_matches_source_bound_gold():
    result = evaluate_table(candidate(), gold())

    assert result.decision == "matches-gold"
    assert result.structure_f1 == result.text_accuracy == result.exact_cell_accuracy == 1


def test_source_mismatch_cannot_pass_even_with_identical_cells():
    payload = candidate().model_dump()
    payload["source"]["source_checksum"] = "b" * 64

    result = evaluate_table(VisualTableDraft.model_validate(payload), gold())

    assert not result.source_matches
    assert result.decision == "requires-review-or-model-improvement"


def test_manifest_blocks_single_perfect_sample_and_emits_no_content():
    payload = candidate().model_dump() | {
        "schema_version": "visual-table-draft-v1",
        "publication_status": "requires-schema-validation-and-teacher-review",
    }
    report = evaluate_manifest(
        [payload],
        VisualTableGoldManifest.model_validate(
            {"schema_version": "visual-table-gold-v1", "tables": [gold().model_dump()]}
        ),
    )

    assert report["candidate_decision"] == "blocked_insufficient_gold_samples"
    assert report["contains_document_content"] is False
    assert report["evaluations"][0]["decision"] == "matches-gold"


def test_manifest_rejects_unexpected_model_field_instead_of_ignoring_it():
    payload = candidate().model_dump() | {
        "schema_version": "visual-table-draft-v1",
        "publication_status": "requires-schema-validation-and-teacher-review",
        "html": "<table>untrusted</table>",
    }
    report = evaluate_manifest(
        [payload],
        VisualTableGoldManifest.model_validate(
            {"schema_version": "visual-table-gold-v1", "tables": [gold().model_dump()]}
        ),
    )

    assert report["invalid_or_duplicate_draft_regions"] == ["table-p46-1"]
    assert report["evaluations"][0]["decision"] == "missing-candidate"


def test_symbol_quality_gate_detects_a_wrong_critical_glyph():
    payload = candidate().model_dump() | {
        "schema_version": "visual-table-draft-v1",
        "publication_status": "requires-schema-validation-and-teacher-review",
    }
    reference = gold().model_dump()
    reference["cells"][1]["text"] = "∈"
    payload["cells"][1]["text"] = "!"

    report = evaluate_manifest(
        [payload],
        VisualTableGoldManifest.model_validate({"schema_version": "visual-table-gold-v1", "tables": [reference]}),
    )

    assert report["symbol_quality"] == {
        "report_type": "table-symbol-critical-quality-v1",
        "contains_document_content": False,
        "symbol_critical_cells": 1,
        "symbol_exact_accuracy": 0.0,
        "missing_symbol_cells": 0,
        "decision": "symbol-gate-blocked",
    }
