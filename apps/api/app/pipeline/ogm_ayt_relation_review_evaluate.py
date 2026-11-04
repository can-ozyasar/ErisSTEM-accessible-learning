"""Validate blind relation-review batches and score retrieval methods privately."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ..history_rag_hybrid import evaluate_rankings

QUEUE_SCHEMA = "ogm-ayt-relation-discovery-review-queue-v1"
RANKING_SCHEMA = "ogm-ayt-relation-retrieval-rankings-v1"
METHODS = ("bm25", "bge_dense", "bge_sparse", "rrf")
DIAGNOSTICS = {"direct_support", "multi_atom_candidate", "indirect_only", "irrelevant"}
QUESTION_DIAGNOSES = {"direct_evidence_found", "multi_atom_required", "candidate_set_insufficient", "indirect_only"}


def _key(item: dict) -> str:
    return f'{item["source_checksum"]}:{item["chunk_id"]}'


def merge_and_evaluate(queue: dict, rankings: dict, batches: list[dict]) -> dict:
    if queue.get("schema") != QUEUE_SCHEMA or rankings.get("schema") != RANKING_SCHEMA:
        raise ValueError("İlişki inceleme kuyruğu ve Kaggle ranking gerekli")
    for key in ("source_checksum", "corpus_checksum"):
        if rankings.get(key) != queue.get(key):
            raise ValueError("Kuyruk ve Kaggle ranking kaynak sürümleri eşleşmiyor")
    expected = {row["candidate_id"]: {_key(item) for item in row["suggestions"]}
                for row in queue.get("proposals", [])}
    reviews = []
    for batch in batches:
        if batch.get("schema") != "relation-agent-review-v1":
            raise ValueError("Ajan inceleme şeması geçersiz")
        for key in ("source_checksum", "corpus_checksum"):
            if batch.get(key) != queue.get(key):
                raise ValueError("Ajan incelemesi kaynak sürümüyle eşleşmiyor")
        for key in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"):
            if batch.get(key) is not False:
                raise ValueError(f"Ajan incelemesinde {key} false olmalı")
        reviews.extend(batch.get("reviews", []))
    if len(reviews) != len(expected) or {row.get("candidate_id") for row in reviews} != set(expected):
        raise ValueError("Ajan incelemeleri her kalibrasyon sorusunu tam bir kez kapsamalı")
    labels = []
    by_question_diagnosis = Counter()
    by_card_diagnostic = Counter()
    for review in reviews:
        candidate_id = review["candidate_id"]
        if (not review.get("reviewed") or not review.get("crop_checked") or not review.get("coverage_complete")
                or review.get("reviewer_kind") != "history_teacher_agent_v1" or not review.get("reviewer")):
            raise ValueError("Ajan incelemesinde PDF kırpımı ve inceleyen kimliği gerekli")
        judgments = review.get("judgments", [])
        keys = [item.get("source_key") for item in judgments]
        if len(keys) != len(set(keys)) or set(keys) != expected[candidate_id]:
            raise ValueError("Ajan incelemesi kaynak kartlarını eksiksiz ve tekil kapsamalı")
        if any(item.get("verdict") not in {"support", "wrong"} or item.get("diagnostic") not in DIAGNOSTICS
               for item in judgments):
            raise ValueError("Ajan kart kararı veya tanısı geçersiz")
        support = {item["source_key"] for item in judgments if item["verdict"] == "support"}
        if any(item["diagnostic"] != "direct_support" for item in judgments if item["verdict"] == "support"):
            raise ValueError("Destekleyici kanıt doğrudan destek tanısı taşımalı")
        if review.get("abstain") is not (not bool(support)):
            raise ValueError("Çekimserlik doğrudan kanıt kararıyla çelişiyor")
        diagnosis = review.get("question_diagnosis")
        if diagnosis not in QUESTION_DIAGNOSES:
            raise ValueError("Soru tanısı geçersiz")
        if bool(support) != (diagnosis == "direct_evidence_found"):
            raise ValueError("Soru tanısı doğrudan kanıt kararıyla çelişiyor")
        by_question_diagnosis[diagnosis] += 1
        by_card_diagnostic.update(item["diagnostic"] for item in judgments)
        labels.append({"id": candidate_id, "gold_source_ids": sorted(support),
                       "wrong_source_ids": [item["source_key"] for item in judgments if item["verdict"] == "wrong"],
                       "abstain": not bool(support)})
    method_metrics = {}
    for method in METHODS:
        candidate_rankings = {candidate_id: values[method] for candidate_id, values in rankings["rankings"].items()}
        method_metrics[method] = evaluate_rankings(labels, candidate_rankings, latencies_ms=[])
    return {
        "schema": "ogm-ayt-relation-retrieval-review-eval-v1",
        "source_checksum": queue["source_checksum"], "corpus_checksum": queue["corpus_checksum"],
        "reviewed_question_count": len(reviews), "method_metrics": method_metrics,
        "question_diagnoses": dict(sorted(by_question_diagnosis.items())),
        "card_diagnostics": dict(sorted(by_card_diagnostic.items())),
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Private calibration only. Agent review is recorded distinctly from human approval and cannot enable runtime or QLoRA.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--batch", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    output = merge_and_evaluate(load(args.queue), load(args.rankings), [load(path) for path in args.batch])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"reviewed_question_count": output["reviewed_question_count"],
                      "question_diagnoses": output["question_diagnoses"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
