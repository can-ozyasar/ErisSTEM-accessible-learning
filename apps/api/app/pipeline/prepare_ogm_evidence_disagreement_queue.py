"""Keep only questions whose independent evidence reviews disagree."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(queue: dict, first: dict, second: dict) -> dict:
    if queue.get("schema") != "ogm-ayt-real-question-evidence-queue-v1":
        raise ValueError("güncel MEB kanıt kuyruğu gerekli")
    expected = {row["candidate_id"] for row in queue["proposals"]}
    first_by_id = {row["candidate_id"]: row for row in first.get("reviews", [])}
    second_by_id = {row["candidate_id"]: row for row in second.get("reviews", [])}
    if set(first_by_id) != expected or set(second_by_id) != expected:
        raise ValueError("iki denetim de tüm soruları kapsamalı")
    ids = {key for key in expected if first_by_id[key]["coverage_complete"] != second_by_id[key]["coverage_complete"]}
    return {**queue, "schema": "ogm-ayt-real-question-evidence-disagreement-queue-v1",
            "proposals": [row for row in queue["proposals"] if row["candidate_id"] in ids],
            "question_count": len(ids), "comparison": {"first_review": first.get("queue_checksum"), "second_review": second.get("queue_checksum")},
            "notice": "Only disagreement cases. Third review is required before adding newly supported cases to a pilot."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True); parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    result = build(load(args.queue), load(args.first), load(args.second)); args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
