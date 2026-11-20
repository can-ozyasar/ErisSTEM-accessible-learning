"""Merge independently reviewed original-question drafts without runtime approval."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(draft_batches: list[dict], review_batches: list[dict]) -> dict:
    drafts: dict[str, dict] = {}
    corpus_checksum = queue_checksum = None
    for batch in draft_batches:
        if batch.get("schema") != "deepseek-original-question-drafts-v1":
            raise ValueError("Özgün soru taslak paketi gerekli")
        identity = (batch.get("corpus_checksum"), batch.get("queue_checksum"))
        if not all(isinstance(value, str) and value for value in identity):
            raise ValueError("Taslak kaynak kimliği gerekli")
        if corpus_checksum is None:
            corpus_checksum, queue_checksum = identity
        elif identity != (corpus_checksum, queue_checksum):
            raise ValueError("Taslak batch kaynak kimlikleri uyuşmuyor")
        for row in batch.get("drafts", []):
            if row.get("id") in drafts or row.get("runtime_enabled") is not False:
                raise ValueError("Taslak kimliği tekrarlı veya runtime durumu geçersiz")
            drafts[row["id"]] = row
    reviews: dict[str, dict] = {}
    for batch in review_batches:
        if (batch.get("schema") != "deepseek-original-question-review-v1"
                or (batch.get("corpus_checksum"), batch.get("queue_checksum")) != (corpus_checksum, queue_checksum)):
            raise ValueError("Bağımsız inceleme kaynak kimliği uyuşmuyor")
        for row in batch.get("reviews", []):
            if row.get("id") in reviews:
                raise ValueError("Bir taslak birden fazla bağımsız inceleme taşıyor")
            reviews[row.get("id")] = row
    if set(drafts) != set(reviews):
        raise ValueError("Her taslak için tam bir bağımsız inceleme gerekli")
    accepted, held = [], []
    for identifier in sorted(drafts):
        record = {"draft": drafts[identifier], "independent_review": reviews[identifier],
                  "source_crop_validation_required": True, "runtime_enabled": False}
        (accepted if reviews[identifier].get("verdict") == "accept_for_source_validation" else held).append(record)
    return {"schema": "ayt-history-original-question-review-gate-v1", "corpus_checksum": corpus_checksum,
            "queue_checksum": queue_checksum, "accepted_for_source_crop_validation": accepted, "held_out": held,
            "summary": {"reviewed": len(drafts), "accepted_for_source_crop_validation": len(accepted), "held_out": len(held)},
            "answer_key_accessed": False, "student_data_accessed": False, "is_human_teacher_approval": False,
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Private reviewed drafts only. Source/crop validation and release checks remain mandatory."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", type=Path, action="append", required=True)
    parser.add_argument("--review", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build([load(path) for path in args.draft], [load(path) for path in args.review])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
