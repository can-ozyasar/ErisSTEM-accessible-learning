"""Select only full-coverage, answer-key-blind evidence-review candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _queue_digest(queue: dict) -> str:
    """Match the checksum emitted by deepseek_ogm_evidence_review."""
    return hashlib.sha256(json.dumps(queue, sort_keys=True).encode()).hexdigest()


def build(queue: dict, review: dict) -> dict:
    if queue.get("schema") != "ogm-ayt-real-question-evidence-queue-v1":
        raise ValueError("OGM gerçek soru kanıt kuyruğu gerekli")
    if review.get("schema") != "deepseek-ogm-ayt-evidence-review-v1":
        raise ValueError("kaynak-kapsam incelemesi gerekli")
    if (review.get("queue_checksum") != _queue_digest(queue)
            or review.get("question_source_checksum") != queue.get("question_source_checksum")
            or review.get("corpus_checksum") != queue.get("corpus_checksum")):
        raise ValueError("inceleme ve kuyruk kaynak zinciri uyuşmuyor")
    if review.get("answer_key_accessed") is not False or review.get("runtime_enabled") is not False:
        raise ValueError("cevap anahtarı erişimli veya runtime incelemesi seçilemez")
    decisions = {row["candidate_id"]: row for row in review.get("reviews", [])}
    if len(decisions) != len(review.get("reviews", [])):
        raise ValueError("yinelenen inceleme kararı")
    selected = [row for row in queue["proposals"] if decisions.get(row["candidate_id"], {}).get("coverage_complete") is True]
    return {
        **queue,
        "question_count": len(selected),
        "proposals": selected,
        "selection": {
            "method": "first_pass_full_coverage_only",
            "parent_queue_checksum": _queue_digest(queue),
            "review_checksum": _digest(review),
            "answer_key_accessed": False,
            "requires_second_independent_review": True,
        },
        "runtime_enabled": False,
        "notice": "First-pass AI complete-coverage candidates only. Every selected item requires a second independent review and PDF crop audit before any runtime decision.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    output = build(load(args.queue), load(args.review))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"question_count": output["question_count"], "runtime_enabled": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
