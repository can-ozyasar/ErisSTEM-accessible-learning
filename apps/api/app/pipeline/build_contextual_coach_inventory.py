"""Create a fail-closed inventory so coach generation never repeats groups."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(pack: dict, drafts: list[dict], reviews: list[dict]) -> dict:
    if pack.get("schema") != "ayt-history-question-bank-training-candidate-v1":
        raise ValueError("Donmuş soru-bankası paketi gerekli")
    expected = {row["id"] for row in pack.get("questions", [])}
    reviewed: dict[str, dict] = {}
    by_question: dict[str, dict] = {}
    for draft in drafts:
        if draft.get("schema") != "deepseek-contextual-source-bound-coaching-drafts-v1":
            continue  # Earlier schema lacks the question text needed by the reviewer.
        if draft.get("corpus_checksum") != pack.get("corpus_checksum") or draft.get("question_bank_checksum") != pack.get("frozen_checksum"):
            raise ValueError("Koçluk taslağı paket sürümü uyuşmuyor")
        for row in draft.get("records", []):
            question_id = row.get("question_id")
            if question_id not in expected or not row.get("question"):
                raise ValueError("Taslak soru kimliği veya soru kökü geçersiz")
            # Inputs are supplied oldest-to-newest. A later, independently
            # reviewed regeneration explicitly supersedes its earlier draft.
            by_question[question_id] = row
    for review in reviews:
        if review.get("schema") != "deepseek-source-bound-coaching-group-review-v1":
            continue
        for row in review.get("reviews", []):
            question_id = row.get("question_id")
            if question_id not in by_question:
                continue
            reviewed[question_id] = row
    accepted = sorted(key for key, row in reviewed.items() if row.get("verdict") == "accept_for_qlora_candidate")
    rejected = sorted(key for key, row in reviewed.items() if row.get("verdict") == "reject")
    missing = sorted(expected - set(reviewed))
    return {"schema": "ayt-history-contextual-coach-inventory-v1", "corpus_checksum": pack["corpus_checksum"],
            "question_bank_checksum": pack["frozen_checksum"], "accepted": accepted, "rejected": rejected, "missing": missing,
            "decisions": {key: {"verdict": row["verdict"], "reason": row.get("reason", "")} for key, row in reviewed.items()},
            "summary": {"total": len(expected), "accepted": len(accepted), "rejected": len(rejected), "missing": len(missing)},
            "notice": "Only contextual drafts carrying question text are counted; superseded artifacts are ignored."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--draft", type=Path, action="append", required=True)
    parser.add_argument("--review", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.pack), [load(path) for path in args.draft], [load(path) for path in args.review])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
