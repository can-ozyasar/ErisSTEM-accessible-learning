"""Merge resumable, answer-key-blind OGM evidence-review batches safely."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REVIEW_SCHEMA = "deepseek-ogm-ayt-evidence-review-v1"


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _queue_digest(queue: dict) -> str:
    """Match deepseek_ogm_evidence_review's published queue checksum exactly."""
    return hashlib.sha256(json.dumps(queue, sort_keys=True).encode()).hexdigest()


def merge(queue: dict, batches: list[dict]) -> dict:
    if queue.get("schema") != "ogm-ayt-real-question-evidence-queue-v1":
        raise ValueError("OGM gerçek soru kanıt kuyruğu gerekli")
    if not batches:
        raise ValueError("en az bir inceleme partisi gerekli")
    queue_checksum = _queue_digest(queue)
    expected = [row["candidate_id"] for row in queue.get("proposals", [])]
    expected_ids = set(expected)
    merged: dict[str, dict] = {}
    reviewers = set()
    for batch in batches:
        if batch.get("schema") != REVIEW_SCHEMA:
            raise ValueError("inceleme partisi şeması geçersiz")
        if (batch.get("queue_checksum") != queue_checksum
                or batch.get("question_source_checksum") != queue.get("question_source_checksum")
                or batch.get("corpus_checksum") != queue.get("corpus_checksum")):
            raise ValueError("inceleme partisi kaynak zinciriyle eşleşmiyor")
        if batch.get("answer_key_accessed") is not False or batch.get("runtime_enabled") is not False:
            raise ValueError("cevap anahtarına erişen veya runtime işaretli parti reddedildi")
        for review in batch.get("reviews", []):
            identifier = review.get("candidate_id")
            if identifier not in expected_ids:
                raise ValueError("inceleme partisi kuyruk dışı soru içeriyor")
            if identifier in merged:
                raise ValueError("aynı soru iki inceleme partisinde tekrarlandı")
            merged[identifier] = review
            reviewers.add(review.get("reviewer", batch.get("model", "unknown")))
    if not merged:
        raise ValueError("inceleme partilerinde karar yok")
    reviews = [merged[identifier] for identifier in expected if identifier in merged]
    complete = sum(item.get("coverage_complete") is True for item in reviews)
    return {
        "schema": REVIEW_SCHEMA,
        "queue_checksum": queue_checksum,
        "question_source_checksum": queue["question_source_checksum"],
        "corpus_checksum": queue["corpus_checksum"],
        "model": ",".join(sorted(str(value) for value in reviewers)),
        "reviews": reviews,
        "summary": {"review_count": len(reviews), "complete": complete, "abstained": len(reviews) - complete,
                    "queue_count": len(expected), "is_complete_queue": len(reviews) == len(expected)},
        "answer_key_accessed": False,
        "is_human_teacher_approval": False,
        "runtime_enabled": False,
        "notice": "Merged answer-key-blind AI reviews only; not human approval or a runtime decision.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = merge(load(args.queue), [load(path) for path in args.reviews])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
