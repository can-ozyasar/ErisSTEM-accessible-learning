"""Merge independently reviewed AYT EA/SÖZ scope metadata without exam text."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FORBIDDEN = {"question_text", "choices", "answer", "answer_key", "worked_explanation", "pdf_path"}


def _number(candidate_id: str) -> int:
    try:
        return int(candidate_id.rsplit(":", 2)[1])
    except (IndexError, ValueError) as error:
        raise ValueError("Soru kimliği numara taşımıyor") from error


def build(pairs: list[tuple[dict, dict]]) -> dict:
    items = []
    for tags, review in pairs:
        if "unit-tags" not in str(tags.get("schema")) or "unit-tags-review" not in str(review.get("schema")):
            raise ValueError("AYT kapsam etiketi ve incelemesi gerekli")
        if tags.get("source_checksum") != review.get("source_checksum"):
            raise ValueError("Etiket ve inceleme sürümü uyuşmuyor")
        rows = {row["candidate_id"]: row for row in tags.get("tags", [])}
        for decision in review.get("reviews", []):
            status = decision.get("decision", decision.get("status"))
            if decision.get("candidate_id") not in rows or status != "approved_for_scope_metadata":
                continue
            row = rows[decision["candidate_id"]]
            if FORBIDDEN & set(row):
                raise ValueError("Ham soru veya yanıt alanı kapsam metadata'sına giremez")
            grade = decision["grade_verified"] if "grade_verified" in decision else decision["grade"]
            unit = decision["unit_verified"] if "unit_verified" in decision else decision["meb_unit_id"]
            relation = (decision["relation_type_verified"] if "relation_type_verified" in decision
                        else decision["relation_type"])
            items.append({"exam_id": row["candidate_id"], "year": row["year"], "test": "AYT",
                          "question_number": _number(row["candidate_id"]), "grade": grade,
                          "unit_id": unit, "concept": row["relation_type"], "relation_type": relation,
                          "visual_dependency": False,
                          "direct_evidence": row["direct_source_likely"] == "likely",
                          "accessible": row["accessibility"] == "text_accessible",
                          "reviewer": "history_teacher_agent_scope_review", "approved": True})
    if len({row["exam_id"] for row in items}) != len(items):
        raise ValueError("Çakışan sınav kimliği")
    return {"schema": "yks-history-metadata-v1", "items": items,
            "answer_key_accessed": False, "worked_explanation_accessed": False,
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Reviewed scope metadata only; source evidence approval remains separate."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tags", type=Path, action="append", required=True)
    parser.add_argument("--review", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.tags) != len(args.review):
        raise ValueError("Her etiket için bir inceleme gerekli")
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(list(zip(map(load, args.tags), map(load, args.review))))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"item_count": len(result["items"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
