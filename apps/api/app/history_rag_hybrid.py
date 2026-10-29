"""Deterministic, review-gated hybrid retrieval utilities.

Heavy BGE-M3 and Qwen reranking run in a private Kaggle experiment.  This
module deliberately contains no model download: it validates the exported
artifact, fuses ranked lists predictably and enforces the measured acceptance
threshold before a local runtime can opt in.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from statistics import median

SCHEMA = "history-rag-hybrid-v1"
ACCEPTANCE = {"recall_at_3": 0.05, "mrr_at_3": 0.03, "p95_ms": 1000}


def approval_checksum(source_checksum: str, approved_ids: Iterable[str]) -> str:
    value = "\n".join([source_checksum, *sorted(set(approved_ids))])
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def rrf_fuse(rankings: dict[str, list[str]], k: int = 60) -> list[dict]:
    """Fuse IDs from named rankers; equal scores resolve by stable ID."""
    if k < 1:
        raise ValueError("RRF k must be positive")
    scores: dict[str, float] = {}
    contributors: dict[str, list[str]] = {}
    for name in sorted(rankings):
        seen: set[str] = set()
        for rank, item_id in enumerate(rankings[name], start=1):
            if not isinstance(item_id, str) or item_id in seen:
                continue
            seen.add(item_id)
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            contributors.setdefault(item_id, []).append(name)
    return [{"id": item_id, "score": round(score, 8), "contributors": contributors[item_id]}
            for item_id, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]


def validate_artifact(artifact: dict, source_checksum: str, approved_ids: Iterable[str]) -> dict:
    """Reject stale or unaccepted Kaggle exports before they reach students."""
    if artifact.get("schema") != SCHEMA:
        raise ValueError("Hibrit getirme yapıtı şeması tanınmıyor")
    if artifact.get("source_checksum") != source_checksum:
        raise ValueError("Hibrit yapıt MEB PDF sürümüyle eşleşmiyor")
    expected = approval_checksum(source_checksum, approved_ids)
    if artifact.get("approval_checksum") != expected:
        raise ValueError("Hibrit yapıtın onaylı kaynak kümesi değişmiş")
    if not artifact.get("accepted"):
        raise ValueError("Hibrit yapıt geliştirme kabul kapısını geçmedi")
    metrics = artifact.get("metrics", {})
    delta = artifact.get("delta_vs_bm25", {})
    if (delta.get("recall_at_3", -1) < ACCEPTANCE["recall_at_3"] or
            delta.get("mrr_at_3", -1) < ACCEPTANCE["mrr_at_3"] or
            delta.get("wrong_evidence_rate", 1) > 0 or
            metrics.get("p95_ms", math.inf) > ACCEPTANCE["p95_ms"]):
        raise ValueError("Hibrit yapıt ölçülmüş kabul eşiğini karşılamıyor")
    return artifact


def _dcg(relevance: list[int]) -> float:
    return sum(value / math.log2(position + 2) for position, value in enumerate(relevance))


def evaluate_rankings(queries: list[dict], rankings: dict[str, list[str]], latencies_ms: list[float]) -> dict:
    """Evaluate private labelled development rankings without answer keys.

    Query labels are evidence IDs and optional `abstain`; no question answer
    labels are accepted by this evaluator.
    """
    if not queries:
        raise ValueError("Değerlendirilecek sorgu yok")
    for query in queries:
        forbidden = {"answer", "answer_key", "answer_label", "correct_choice"} & set(query)
        if forbidden:
            raise ValueError("Cevap anahtarı retrieval değerlendirmesine giremez")
    recall_1 = recall_3 = mrr_3 = ndcg_3 = coverage = abstain_ok = 0.0
    wrong = considered = 0
    for query in queries:
        result = rankings.get(query["id"], [])[:3]
        gold = set(query.get("gold_source_ids", []))
        if query.get("abstain"):
            abstain_ok += float(not result)
            continue
        considered += 1
        hits = [item in gold for item in result]
        recall_1 += float(bool(hits[:1] and hits[0]))
        recall_3 += float(any(hits))
        coverage += float(gold.issubset(set(result)))
        rank = next((i + 1 for i, hit in enumerate(hits) if hit), None)
        mrr_3 += 1 / rank if rank else 0
        ideal = [1] * min(3, len(gold))
        ndcg_3 += _dcg([int(hit) for hit in hits]) / _dcg(ideal) if ideal else 0
        judged_wrong = set(query.get("wrong_source_ids", []))
        wrong += sum(item in judged_wrong for item in result)
    normalizer = max(1, considered)
    ordered_latency = sorted(latencies_ms)
    p95 = ordered_latency[max(0, math.ceil(len(ordered_latency) * .95) - 1)] if ordered_latency else 0
    return {"query_count": len(queries), "answerable_count": considered,
            "recall_at_1": round(recall_1 / normalizer, 4), "recall_at_3": round(recall_3 / normalizer, 4),
            "mrr_at_3": round(mrr_3 / normalizer, 4), "ndcg_at_3": round(ndcg_3 / normalizer, 4),
            "evidence_coverage_at_3": round(coverage / normalizer, 4),
            "wrong_evidence_rate": round(wrong / max(1, len(queries) * 3), 4),
            "correct_abstention": round(abstain_ok / max(1, sum(bool(q.get("abstain")) for q in queries)), 4),
            "p50_ms": round(median(latencies_ms), 2) if latencies_ms else 0,
            "p95_ms": round(p95, 2)}


def acceptance_decision(baseline: dict, candidate: dict) -> dict:
    delta = {key: round(candidate.get(key, 0) - baseline.get(key, 0), 4)
             for key in ("recall_at_3", "mrr_at_3", "wrong_evidence_rate")}
    accepted = (delta["recall_at_3"] >= ACCEPTANCE["recall_at_3"] and
                delta["mrr_at_3"] >= ACCEPTANCE["mrr_at_3"] and
                delta["wrong_evidence_rate"] <= 0 and
                candidate.get("p95_ms", math.inf) <= ACCEPTANCE["p95_ms"])
    return {"accepted": accepted, "delta_vs_bm25": delta, "thresholds": ACCEPTANCE}
