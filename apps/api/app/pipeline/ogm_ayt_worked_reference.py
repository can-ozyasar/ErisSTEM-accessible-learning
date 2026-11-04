"""Register worked-explanation pages as teacher-only private references."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "ogm-ayt-worked-reference-v1"


def build(scope: dict, classification: dict) -> dict:
    if scope.get("schema") != "ogm-ayt-pilot-pool-scope-v1":
        raise ValueError("OGM pilot kapsamı şeması gerekli")
    if classification.get("schema") != "ogm-ayt-page-classification-v1":
        raise ValueError("OGM sayfa sınıflandırması gerekli")
    by_page = {row["page"]: row for row in classification.get("pages", [])}
    units = []
    for unit in scope.get("units", []):
        page = max(unit["test_pages"]) + 1
        references = []
        while by_page.get(page, {}).get("category") == "solved_or_explained":
            references.append(page)
            page += 1
        units.append({"topic": unit["topic"], "test_pages": unit["test_pages"],
                      "teacher_only_reference_pages": references,
                      "reference_status": "available" if references else "not_available_without_answer_key"})
    return {"schema": SCHEMA, "source_checksum": scope["source_checksum"], "units": units,
            "answer_key_accessed": False, "worked_explanation_exported": False,
            "notice": "References are for private teacher review only; they cannot be used in runtime, retrieval, coaching targets or QLoRA exports."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--classification", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.scope.read_text(encoding="utf-8")),
                   json.loads(args.classification.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
