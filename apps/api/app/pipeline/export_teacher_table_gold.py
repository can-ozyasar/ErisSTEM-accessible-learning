"""Export only teacher-approved private table reviews as Gold references."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..job_store import TableReviewStore, make_session_factory
from .visual_table_benchmark import (
    GOLD_SCHEMA_VERSION,
    MINIMUM_TABLE_GOLD_SAMPLES,
    VisualTableGoldManifest,
    evaluate_manifest,
)


def teacher_approved_gold(tables: TableReviewStore) -> tuple[dict, dict]:
    """Build a strict Gold manifest only from teacher-approved records.

    The returned report deliberately contains no cell text. Callers write the
    private Gold manifest only after the minimum-sample gate is met.
    """
    approved = tables.list_teacher_approved()
    manifest = {
        "schema_version": GOLD_SCHEMA_VERSION,
        "tables": [
            {
                "schema_version": GOLD_SCHEMA_VERSION,
                "kind": "table",
                "source": item.draft_payload["source"],
                "cells": [
                    {key: cell[key] for key in ("row", "column", "role", "text")}
                    for cell in item.draft_payload["cells"]
                ],
            }
            for item in approved
        ],
    }
    report = {
        "report_type": "teacher-approved-table-gold-export-v1",
        "contains_document_content": False,
        "approved_tables": len(approved),
        "minimum_gold_samples": MINIMUM_TABLE_GOLD_SAMPLES,
        "status": "ready" if len(approved) >= MINIMUM_TABLE_GOLD_SAMPLES else "blocked_insufficient_teacher_approved_tables",
        "region_ids": [item.draft_payload["source"]["region_id"] for item in approved],
    }
    if report["status"] == "ready":
        VisualTableGoldManifest.model_validate(manifest)
    return manifest, report


def teacher_approved_quality_report(tables: TableReviewStore) -> dict:
    """Score immutable pre-review candidates against teacher-approved Gold."""
    manifest, export = teacher_approved_gold(tables)
    if export["status"] != "ready":
        return {
            "report_type": "teacher-approved-vector-native-quality-v1",
            "contains_document_content": False,
            "status": export["status"],
        }
    approved = tables.list_teacher_approved()
    legacy = [
        item.id
        for item in approved
        if any("confidence" not in cell for cell in item.candidate_payload.get("cells", []))
    ]
    if legacy:
        return {
            "report_type": "teacher-approved-vector-native-quality-v1",
            "contains_document_content": False,
            "status": "blocked_missing_immutable_candidate",
            "legacy_record_count": len(legacy),
        }
    gold = VisualTableGoldManifest.model_validate(manifest)
    candidates = [
        {
            key: item.candidate_payload[key]
            for key in ("schema_version", "publication_status", "kind", "source", "cells", "confidence")
        }
        for item in approved
    ]
    return {
        "report_type": "teacher-approved-vector-native-quality-v1",
        "contains_document_content": False,
        "status": "completed",
        "evaluation": evaluate_manifest(candidates, gold),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export teacher-approved private table Gold manifest")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    tables = TableReviewStore(make_session_factory())
    manifest, report = teacher_approved_gold(tables)
    report["candidate_quality"] = teacher_approved_quality_report(tables)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["status"] == "ready":
        args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
