"""Project a validated rank-blind review to pool-limited retrieval labels.

It intentionally refuses to call these labels a full-corpus benchmark: only
the reviewed BM25 pool is labelled, so new dense/RRF candidates remain
unjudged until added to the same PDF-review pool.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .validate_ayt_history_retrieval_pdf_review import validate


def build(template: dict, completed: dict, baseline: dict) -> dict:
    validation = validate(template, completed)
    if (baseline.get("schema") != "ayt-history-provisional-atom-bm25-baseline-v1" or baseline.get("k") != 3
            or baseline.get("candidate_checksum") != validation["candidate_checksum"]
            or baseline.get("corpus_checksum") != validation["corpus_checksum"]
            or baseline.get("split_checksum") != validation["split_checksum"]):
        raise ValueError("Doğrulanmış incelemeyle eşleşen top-3 baseline gerekli")
    baseline_cases = {case.get("id"): case for case in baseline.get("cases", [])}
    reviewed = {row.get("id"): row for row in completed.get("reviews", [])}
    if set(baseline_cases) != set(reviewed) or len(reviewed) != 24:
        raise ValueError("Baseline ve inceleme aynı 24 kilitli soruyu içermeli")
    labels = []
    for identifier in sorted(reviewed):
        row, ranked = reviewed[identifier], baseline_cases[identifier].get("retrieved_atom_ids")
        cards = {card.get("source_key"): card for card in row.get("cards", [])}
        if not isinstance(ranked, list) or set(cards) != set(ranked):
            raise ValueError("İnceleme kartları baseline top-3 ile tam eşleşmeli")
        relevant = [source_key for source_key in ranked if cards[source_key]["decision"] == "relevant"]
        wrong = [source_key for source_key in ranked if cards[source_key]["decision"] == "wrong"]
        insufficient = [source_key for source_key in ranked if cards[source_key]["decision"] == "insufficient"]
        labels.append({"id": identifier, "case_decision": row["case_decision"],
                       "relevant_source_ids": relevant, "wrong_source_ids": wrong,
                       "insufficient_source_ids": insufficient})
    counts = {"sufficient": sum(row["case_decision"] == "sufficient" for row in labels),
              "insufficient": sum(row["case_decision"] == "insufficient" for row in labels),
              "review_required": sum(row["case_decision"] == "review_required" for row in labels)}
    return {"schema": "ayt-history-pool-limited-pdf-retrieval-labels-v1",
            "candidate_checksum": validation["candidate_checksum"], "corpus_checksum": validation["corpus_checksum"],
            "split_checksum": validation["split_checksum"], "review_validation_checksum": validation["completed_checksum"],
            "labels": labels, "summary": {"query_count": len(labels), "case_decisions": counts,
                                                "relevant_cards": sum(len(row["relevant_source_ids"]) for row in labels),
                                                "wrong_cards": sum(len(row["wrong_source_ids"]) for row in labels),
                                                "insufficient_cards": sum(len(row["insufficient_source_ids"]) for row in labels)},
            "metrics_ready": False, "runtime_enabled": False, "qlora_enabled": False,
            "is_human_teacher_approval": False,
            "notice": "Pool-limited labels only. Dense/RRF candidates outside the reviewed BM25 pool are unjudged; therefore this artifact cannot calculate a fair full-corpus comparison or select a runtime retriever."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--completed", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.template), load(args.completed), load(args.baseline))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
