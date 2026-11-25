"""Require two matching source-only reviews before a question enters the pilot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(queue: dict, first: dict, second: dict, third: dict) -> dict:
    if queue.get("schema") != "ogm-ayt-real-question-evidence-queue-v1":
        raise ValueError("güncel MEB kanıt kuyruğu gerekli")
    by_id = {r["candidate_id"]: r for r in queue["proposals"]}
    reviews = [{r["candidate_id"]: r for r in batch.get("reviews", [])} for batch in (first, second, third)]
    if set(reviews[0]) != set(by_id) or set(reviews[1]) != set(by_id):
        raise ValueError("ilk iki denetim tüm soruları içermeli")
    merged = []
    for identifier, proposal in by_id.items():
        votes = [reviews[0][identifier], reviews[1][identifier]]
        if votes[0]["coverage_complete"] != votes[1]["coverage_complete"]:
            final = reviews[2].get(identifier)
            if final is not None:
                votes.append(final)
        complete = sum(v["coverage_complete"] for v in votes) >= 2
        support_ids = {item for vote in votes if vote["coverage_complete"] for item in vote["support_ids"]}
        candidates = [{**item, "verdict": "support" if item["id"] in support_ids and complete else "wrong"}
                      for item in proposal["suggestions"]]
        merged.append({"candidate_id": identifier, "question_text": proposal["question_text"],
                       "status": "ai_consensus_complete" if complete else "ai_consensus_abstain",
                       "candidates": candidates, "coverage_complete": complete, "abstain": not complete,
                       "notes": "Two-of-three source-only AI consensus; PDF-crop assets remain available for audit."})
    return {"schema": "ogm-ayt-real-question-evidence-pdf-review-v1", "question_source_checksum": queue["question_source_checksum"],
            "corpus_checksum": queue["corpus_checksum"], "review_count": len(merged), "reviews": merged,
            "reviewer_kind": "deepseek_two_of_three_source_consensus_v1", "is_human_teacher_approval": False,
            "runtime_enabled": False, "notice": "AI consensus only; no claim of human teacher approval."}


def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument('--queue',type=Path,required=True); p.add_argument('--first',type=Path,required=True); p.add_argument('--second',type=Path,required=True); p.add_argument('--third',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); load=lambda x:json.loads(x.read_text(encoding='utf-8'))
    a.output.write_text(json.dumps(build(load(a.queue),load(a.first),load(a.second),load(a.third)),ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__': main()
