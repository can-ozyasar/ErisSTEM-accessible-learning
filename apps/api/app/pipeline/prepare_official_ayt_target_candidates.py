"""Normalize answer-free official AYT candidates for 12th-grade scope review.

This is a discovery input, not an answer source.  It preserves page geometry
so a history teacher can verify the printed question, but does not inspect or
export any answer-key or solution pages.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "official-ayt-target-candidate-pool-v1"
SOURCE_SCHEMA = "ayt-tarih2-candidates-v1"


def _text(question: dict) -> str:
    return " ".join(
        part.get("text", "").strip()
        for part in question.get("parts", [])
        if part.get("kind") in {"stem", "prompt", "statement"} and part.get("text", "").strip()
    )


def _validate_candidate(candidate: dict) -> bool:
    question = candidate.get("question", {})
    choices = question.get("choices", [])
    labels = [choice.get("label") for choice in choices]
    return bool(_text(question)) and labels == list("ABCDE") and all(choice.get("text", "").strip() for choice in choices)


def build(*sources: dict) -> dict:
    rows = []
    seen: set[str] = set()
    for source in sources:
        if source.get("schema") != SOURCE_SCHEMA:
            raise ValueError("Resmî AYT aday şeması geçersiz")
        for candidate in source.get("candidates", []):
            if candidate.get("year_status") != "bound" or candidate.get("candidate_id") in seen:
                continue
            if not _validate_candidate(candidate):
                continue
            seen.add(candidate["candidate_id"])
            question = candidate["question"]
            rows.append({
                "candidate_id": candidate["candidate_id"],
                "source_kind": "official_exam_private",
                "source_checksum": candidate["source_checksum"],
                "test": candidate.get("test"),
                "exam_year": candidate.get("exam_year"),
                "page": candidate["page"],
                "bbox": candidate["bbox"],
                "question": {
                    "stem": _text(question),
                    "choices": [{"label": choice["label"], "text": choice["text"]} for choice in question["choices"]],
                    "visual_dependency": bool(question.get("visuals")),
                },
                "transcription_status": "private_teacher_review_required",
                "answer_key_accessed": False,
                "worked_explanation_accessed": False,
            })
    if not rows:
        raise ValueError("İncelemeye uygun resmî AYT sorusu bulunamadı")
    return {
        "schema": SCHEMA,
        "rows": sorted(rows, key=lambda row: (row["test"], row["exam_year"], row["page"], row["candidate_id"])),
        "candidate_count": len(rows),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Private official-exam discovery only. Exact target section and source evidence require separate teacher PDF-crop review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(*(json.loads(path.read_text(encoding="utf-8")) for path in args.source))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidates": result["candidate_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
