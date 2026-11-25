"""Compute transparent top-3 pooled metrics after blind-card adjudication."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

METHODS = ("bm25", "qwen_dense", "rrf")


def evaluate(ranking: dict[str, Any], labels: dict[str, dict], adjudication: dict[str, Any]) -> dict[str, Any]:
    if ranking.get("ranking_methods") != list(METHODS):
        raise ValueError("BM25, Qwen dense ve RRF sıralamaları gerekli")
    for method in METHODS:
        if labels[method].get("schema") != "ayt-history-pool-limited-pdf-retrieval-labels-v1":
            raise ValueError("Havuz-sınırlı PDF etiketleri gerekli")
    decisions: dict[tuple[str, str], str] = {}
    for label in labels.values():
        for row in label["labels"]:
            for decision, key in (("relevant", "relevant_source_ids"), ("wrong", "wrong_source_ids"), ("insufficient", "insufficient_source_ids")):
                for atom in row[key]:
                    pair = (row["id"], atom)
                    if pair in decisions and decisions[pair] != decision:
                        continue
                    decisions[pair] = decision
    if adjudication.get("schema") != "ayt-history-retrieval-label-conflict-adjudication-v1":
        raise ValueError("Çelişki adjudication çıktısı gerekli")
    if adjudication["summary"].get("review_required_count"):
        raise ValueError("Çözülmemiş kart çelişkileri varken metrik hesaplanamaz")
    for row in adjudication["records"]:
        decisions[(row["id"], row["source_key"])] = row["resolution"]
    rankings = ranking["rankings"]
    metric_rows = {method: [] for method in METHODS}
    for identifier, by_method in rankings.items():
        relevant = {atom for (question, atom), decision in decisions.items() if question == identifier and decision == "relevant"}
        if not relevant:
            raise ValueError("Her kilitli soru için en az bir relevant kart gerekli")
        for method in METHODS:
            top = by_method[method][:3]
            if any((identifier, atom) not in decisions for atom in top):
                raise ValueError("Her top-3 aday ortak inceleme havuzunda etiketli olmalı")
            gains = [1 if atom in relevant else 0 for atom in top]
            first = next((position for position, gain in enumerate(gains, 1) if gain), None)
            dcg = sum(gain / math.log2(position + 1) for position, gain in enumerate(gains, 1))
            ideal = sum(1 / math.log2(position + 1) for position in range(1, min(3, len(relevant)) + 1))
            metric_rows[method].append({"recall_1": gains[0] / len(relevant), "recall_3": sum(gains) / len(relevant),
                                        "mrr_3": 0 if first is None else 1 / first, "ndcg_3": dcg / ideal,
                                        "top1_wrong": decisions[(identifier, top[0])] == "wrong",
                                        "top1_insufficient": decisions[(identifier, top[0])] == "insufficient"})
    summary = {}
    for method, rows in metric_rows.items():
        summary[method] = {key: round(sum(float(row[key]) for row in rows) / len(rows), 4)
                           for key in ("recall_1", "recall_3", "mrr_3", "ndcg_3")}
        summary[method].update({"top1_wrong_rate": round(sum(row["top1_wrong"] for row in rows) / len(rows), 4),
                                "top1_insufficient_rate": round(sum(row["top1_insufficient"] for row in rows) / len(rows), 4)})
    return {"schema": "ayt-history-pooled-top3-retrieval-evaluation-v1", "source_checksum": ranking["source_checksum"],
            "corpus_checksum": ranking["corpus_checksum"], "query_count": len(rankings), "methods": summary,
            "metric_scope": "24 locked queries; union of the three methods' top-3 PDF cards, agent-labelled and conflict-adjudicated",
            "human_teacher_approval": False, "runtime_enabled": False,
            "notice": "Comparable pooled top-3 evidence metrics, not a full-corpus relevance benchmark or a human validation."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ranking", type=Path, required=True)
    parser.add_argument("--bm25-labels", type=Path, required=True)
    parser.add_argument("--dense-labels", type=Path, required=True)
    parser.add_argument("--rrf-labels", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    output = evaluate(load(args.ranking), {"bm25": load(args.bm25_labels), "qwen_dense": load(args.dense_labels), "rrf": load(args.rrf_labels)}, load(args.adjudication))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
