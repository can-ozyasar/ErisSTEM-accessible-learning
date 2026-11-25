"""Project an answer-key-blind review onto a provenance-checked queue subset."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _queue_digest(queue: dict) -> str:
    return hashlib.sha256(json.dumps(queue, sort_keys=True).encode()).hexdigest()


def build(parent_queue: dict, subset_queue: dict, review: dict) -> dict:
    if parent_queue.get("schema") != "ogm-ayt-real-question-evidence-queue-v1" or subset_queue.get("schema") != "ogm-ayt-real-question-evidence-queue-v1":
        raise ValueError("OGM gerçek soru kanıt kuyrukları gerekli")
    if review.get("schema") != "deepseek-ogm-ayt-evidence-review-v1":
        raise ValueError("kaynak-kapsam incelemesi gerekli")
    if review.get("queue_checksum") != _queue_digest(parent_queue):
        raise ValueError("ana inceleme ana kuyrukla uyuşmuyor")
    if (review.get("question_source_checksum") != subset_queue.get("question_source_checksum")
            or review.get("corpus_checksum") != subset_queue.get("corpus_checksum")):
        raise ValueError("inceleme ve alt küme kaynak zinciri uyuşmuyor")
    if review.get("answer_key_accessed") is not False or review.get("runtime_enabled") is not False:
        raise ValueError("cevap anahtarı erişimli veya runtime incelemesi seçilemez")
    by_id = {row["candidate_id"]: row for row in review.get("reviews", [])}
    selected_ids = [row["candidate_id"] for row in subset_queue.get("proposals", [])]
    if len(by_id) != len(review.get("reviews", [])) or not set(selected_ids) <= set(by_id):
        raise ValueError("alt kümedeki her soru için tek ana inceleme gerekli")
    projected = [by_id[identifier] for identifier in selected_ids]
    complete = sum(row.get("coverage_complete") is True for row in projected)
    return {**review, "queue_checksum": _queue_digest(subset_queue), "reviews": projected,
            "summary": {"review_count": len(projected), "complete": complete, "abstained": len(projected) - complete,
                        "projected_from_queue_checksum": _queue_digest(parent_queue)},
            "runtime_enabled": False,
            "notice": "Projection of answer-key-blind first-pass decisions onto a subset; not a new review or runtime decision."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-queue", type=Path, required=True)
    parser.add_argument("--subset-queue", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    output = build(load(args.parent_queue), load(args.subset_queue), load(args.review))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
