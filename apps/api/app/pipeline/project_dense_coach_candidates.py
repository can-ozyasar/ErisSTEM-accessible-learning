"""Project reviewed dense-retrieval cards into source-bound coach candidates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(queue: dict, reviews: list[dict]) -> dict:
    if queue.get("schema") != "ogm-ayt-relation-discovery-review-queue-v1":
        raise ValueError("AYT ilişki inceleme kuyruğu gerekli")
    by_id = {row["candidate_id"]: row for row in queue.get("proposals", [])}
    labelled: dict[str, dict] = {}
    for batch in reviews:
        if batch.get("schema") != "deepseek-relation-retrieval-review-v1":
            raise ValueError("DeepSeek retrieval inceleme çıktısı gerekli")
        for key in ("source_checksum", "corpus_checksum"):
            if batch.get(key) != queue.get(key):
                raise ValueError("İnceleme ve kuyruk kaynak sürümü eşleşmiyor")
        for row in batch.get("reviews", []):
            if row.get("candidate_id") in labelled:
                raise ValueError("Soru birden fazla DeepSeek incelemesi taşıyor")
            labelled[row.get("candidate_id")] = row
    if set(labelled) != set(by_id):
        raise ValueError("Her retrieval sorusu için tam bir DeepSeek incelemesi gerekli")
    candidates = []
    for question_id, proposal in sorted(by_id.items()):
        review = labelled[question_id]
        cards = {f'{row["source_checksum"]}:{row["chunk_id"]}': row for row in proposal["suggestions"]}
        support = [cards[row["source_key"]] for row in review["judgments"] if row["verdict"] == "support"]
        diagnosis = review["question_diagnosis"]
        usable = diagnosis in {"direct_evidence_found", "multi_atom_required"} and bool(support)
        candidates.append({
            "question_id": question_id, "status": "coach_candidate" if usable else "abstain_source_insufficient",
            "evidence_mode": "multi_atom" if diagnosis == "multi_atom_required" else "direct",
            "source_ids": [f'{row["source_checksum"]}:{row["chunk_id"]}' for row in support],
            "evidence": [{"source_checksum": row["source_checksum"], "chunk_id": row["chunk_id"],
                          "page": row["page"], "bbox": row["bbox"], "text": row["text"]} for row in support],
            "review": {"reviewer_kind": review["reviewer_kind"], "source_text_checked": True,
                       "human_teacher_approval": False, "question_diagnosis": diagnosis},
        })
    return {"schema": "ayt-dense-coach-candidates-v1", "source_checksum": queue["source_checksum"],
            "corpus_checksum": queue["corpus_checksum"], "candidates": candidates,
            "summary": {"coach_candidate_count": sum(row["status"] == "coach_candidate" for row in candidates),
                        "abstain_count": sum(row["status"] != "coach_candidate" for row in candidates)},
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Source-text-reviewed coach candidates only; not human source approval or an active-exam answer path."}


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
