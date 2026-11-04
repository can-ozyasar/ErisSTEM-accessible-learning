"""Score private development rankings with the version-2 retrieval contract.

The output is an experiment report. A teacher-reviewed, checksum-bound
artifact must be created separately before any product path can use it.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median

ROOT = Path("/kaggle/input/history-rag-hybrid-dev-v1")
LABELS = ROOT / "history-rag-hybrid-dev-v1.json"
RANKS = Path("/kaggle/working/history-rag-hybrid-report.json")
OUT = Path("/kaggle/working/history-rag-hybrid-gate.json")
FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice"}


def _dcg(relevance: list[int]) -> float:
    return sum(value / math.log2(place + 2) for place, value in enumerate(relevance))


def score(queries: list[dict], rankings: dict[str, list[str]], latency: list[float]) -> dict:
    if not queries:
        raise ValueError("Development queries required")
    recall_1 = recall_3 = hit_1 = hit_3 = mrr = ndcg = coverage = abstain_ok = 0.0
    wrong = judged = unjudged = answerable = 0
    for query in queries:
        if FORBIDDEN & set(query):
            raise ValueError("Answer labels are forbidden")
        result = rankings.get(query["id"], [])[:3]
        gold = set(query.get("gold_source_ids", []))
        if query.get("abstain"):
            if gold:
                raise ValueError("Abstain item cannot have gold sources")
            abstain_ok += float(not result)
            continue
        if not gold:
            raise ValueError("Answerable item needs gold sources")
        answerable += 1
        wrong_ids = set(query.get("wrong_source_ids", []))
        if gold & wrong_ids:
            raise ValueError("Gold and wrong source labels overlap")
        hits = [item in gold for item in result]
        recall_1 += len(gold & set(result[:1])) / len(gold)
        recall_3 += len(gold & set(result)) / len(gold)
        hit_1 += float(bool(hits[:1] and hits[0]))
        hit_3 += float(any(hits))
        coverage += float(gold.issubset(set(result)))
        rank = next((place + 1 for place, hit in enumerate(hits) if hit), None)
        mrr += 1 / rank if rank else 0
        ideal = [1] * min(3, len(gold))
        ndcg += _dcg([int(hit) for hit in hits]) / _dcg(ideal) if ideal else 0
        wrong += sum(item in wrong_ids for item in result)
        judged += sum(item in gold or item in wrong_ids for item in result)
        unjudged += sum(item not in gold and item not in wrong_ids for item in result)
    n = max(1, answerable)
    ordered = sorted(latency)
    p95 = ordered[max(0, math.ceil(len(ordered) * .95) - 1)] if ordered else 0
    return {
        "metric_schema": "history-rag-retrieval-metrics-v2",
        "query_count": len(queries), "answerable_count": answerable,
        "judged_result_count": judged, "unjudged_result_count": unjudged,
        "wrong_evidence_count": wrong,
        "hit_at_1": round(hit_1 / n, 4), "hit_at_3": round(hit_3 / n, 4),
        "recall_at_1": round(recall_1 / n, 4), "recall_at_3": round(recall_3 / n, 4),
        "mrr_at_3": round(mrr / n, 4), "ndcg_at_3": round(ndcg / n, 4),
        "evidence_coverage_at_3": round(coverage / n, 4),
        "wrong_evidence_rate": round(wrong / max(1, judged), 4),
        "correct_abstention": round(
            abstain_ok / max(1, sum(bool(query.get("abstain")) for query in queries)), 4),
        "p50_ms": round(median(latency), 2) if latency else 0,
        "p95_ms": round(p95, 2),
    }


def main() -> None:
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    run = json.loads(RANKS.read_text(encoding="utf-8"))
    if labels.get("split") != "development" or labels.get("schema") != "history-rag-hybrid-dev-v1":
        raise ValueError("Private development labels required")
    if run.get("schema") != "history-rag-hybrid-result-v2":
        raise ValueError("Version-2 rankings with per-method timings required")
    if (run.get("input_source_checksum") != labels.get("source_checksum")
            or run.get("input_approval_checksum") != labels.get("approval_checksum")):
        raise ValueError("Source or approval revision changed")
    variants = {
        method: {qid: value[method] for qid, value in run["rankings"].items() if method in value}
        for method in ("bm25", "dense", "rrf")
    }
    results = {
        method: score(labels["queries"], ranking, run["latencies_by_method_ms"][method])
        for method, ranking in variants.items() if ranking
    }
    baseline = results["bm25"]
    comparisons = {}
    for method, result in results.items():
        comparisons[method] = {
            "delta_vs_bm25": {key: round(result[key] - baseline[key], 4)
                              for key in ("recall_at_3", "mrr_at_3",
                                          "evidence_coverage_at_3", "wrong_evidence_rate",
                                          "wrong_evidence_count",
                                          "correct_abstention", "p95_ms")},
            "review_required": True,
        }
    OUT.write_text(json.dumps({
        "schema": "history-rag-hybrid-gate-v2",
        "source_checksum": labels["source_checksum"],
        "approval_checksum": labels["approval_checksum"],
        "metrics": results, "comparisons": comparisons,
        "accepted": False,
        "notice": "Experiment only. Teacher review and local latency are required for product adoption.",
    }, ensure_ascii=False), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
