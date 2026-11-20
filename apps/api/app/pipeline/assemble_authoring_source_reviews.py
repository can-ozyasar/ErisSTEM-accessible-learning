"""Merge complete AI source reviews into a fail-closed PDF-crop review queue."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(queue: dict, batches: list[dict]) -> dict:
    if queue.get("schema") != "ayt-history-original-authoring-queue-v1":
        raise ValueError("Özgün soru yazım kuyruğu gerekli")
    if not isinstance(queue.get("queue_checksum"), str) or len(queue["queue_checksum"]) != 64:
        raise ValueError("Kuyruk checksum'ı gerekli")
    cards = {card["id"]: card for card in queue.get("cards", [])}
    reviews: dict[str, dict] = {}
    for batch in batches:
        if (batch.get("schema") != "deepseek-original-authoring-source-review-v1"
                or batch.get("corpus_checksum") != queue.get("corpus_checksum")
                or batch.get("queue_checksum") != queue.get("queue_checksum")):
            raise ValueError("Kaynak inceleme sürümü, corpus veya kuyruk checksum uyuşmuyor")
        for row in batch.get("reviews", []):
            if row.get("id") in reviews:
                raise ValueError("Bir kaynak kartı birden fazla inceleme taşıyor")
            reviews[row.get("id")] = row
    if set(reviews) != set(cards):
        raise ValueError("Her kaynak kartı için tam bir AI incelemesi gerekli")
    accepted, held = [], []
    for card_id, card in sorted(cards.items()):
        review = reviews[card_id]
        record = {"card": card, "ai_review": review, "pdf_crop_review_required": True,
                  "runtime_enabled": False, "question_authoring_enabled": False}
        (accepted if review["verdict"] == "direct_fact" and review["text_only_candidate"] else held).append(record)
    return {
        "schema": "ayt-history-authoring-source-gate-v1", "corpus_checksum": queue["corpus_checksum"],
        "queue_checksum": queue["queue_checksum"],
        "accepted_for_pdf_crop_review": accepted, "held_out": held,
        "summary": {"reviewed": len(reviews), "accepted_for_pdf_crop_review": len(accepted), "held_out": len(held)},
        "answer_key_accessed": False, "worked_explanation_accessed": False, "student_data_accessed": False,
        "is_human_teacher_approval": False, "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Only a PDF-crop review queue. Accepted cards are not approved questions or student evidence.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--review", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.queue), [load(path) for path in args.review])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
