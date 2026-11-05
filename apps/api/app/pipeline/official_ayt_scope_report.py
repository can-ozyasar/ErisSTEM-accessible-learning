"""Derive a conservative AYT scope decision from reviewed metadata only."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def build(tags: dict, review: dict) -> dict:
    if tags.get("schema") != "official-ayt-2022-2026-unit-tags-v1":
        raise ValueError("Resmî AYT etiketleri gerekli")
    if review.get("schema") != "official-ayt-2022-2026-unit-tags-review-v1":
        raise ValueError("Bağımsız kapsam incelemesi gerekli")
    if tags.get("source_checksum") != review.get("source_checksum"):
        raise ValueError("Etiket ve inceleme kaynak sürümleri uyuşmuyor")
    tag_by_id = {row["candidate_id"]: row for row in tags.get("tags", [])}
    reviewed = [row for row in review.get("reviews", []) if row.get("decision") == "approved_for_scope_metadata"]
    if any(row.get("candidate_id") not in tag_by_id for row in reviewed):
        raise ValueError("İnceleme bilinmeyen aday içeriyor")
    grades = Counter(row["grade_verified"] for row in reviewed)
    units = Counter(row["unit_verified"] for row in reviewed)
    grade_ranking = [{"grade": grade, "question_count": count}
                     for grade, count in sorted(grades.items(), key=lambda item: (-item[1], item[0]))]
    unit_ranking = [{"unit_id": unit, "question_count": count}
                    for unit, count in sorted(units.items(), key=lambda item: (-item[1], item[0]))]
    chosen_grade = grade_ranking[0]["grade"] if grade_ranking else None
    chosen_units = [row for row in unit_ranking if row["unit_id"].startswith(f"{chosen_grade}.")]
    # This source is only the SÖZ Tarih-2 series.  A scope may be *provisional*
    # when it is the observed leader, but no six-unit production decision is
    # made until the EA Tarih-1 series is reviewed through the same route.
    return {
        "schema": "official-ayt-scope-report-v1", "source_checksum": tags["source_checksum"],
        "reviewed_metadata_count": len(reviewed), "grade_ranking": grade_ranking,
        "unit_ranking": unit_ranking, "provisional_grade": chosen_grade,
        "provisional_units": chosen_units, "selection_ready": False,
        "missing_evidence": ["2022-2026 AYT EA Tarih-1 metadata review", "six-unit frequency comparison"],
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": ("Scope metadata only. No source evidence, graph edge, runtime RAG or QLoRA approval is implied. "
                   "The existing six-unit pilot remains provisional until EA Tarih-1 is added."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tags", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.tags.read_text(encoding="utf-8")),
                   json.loads(args.review.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"provisional_grade": result["provisional_grade"],
                      "provisional_unit_count": len(result["provisional_units"]),
                      "selection_ready": result["selection_ready"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
