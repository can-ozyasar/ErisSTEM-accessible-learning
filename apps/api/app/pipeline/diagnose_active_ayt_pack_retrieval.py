"""Offline BM25/chunking diagnostics for the active private AYT exam pack.

Gold is only a source/page/bbox localization proxy from the approved pack. This
tool must not enable runtime retrieval or be interpreted as human relevance.
It emits aggregate metrics and hashes, never question text or source excerpts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import time
from pathlib import Path
from statistics import median

from ..history_rag import PreparedBM25

SCHEMA = "active-ayt-pack-bm25-diagnostic-v1"
PACK_SCHEMA = "ayt-history-exam-pack-v1"
CORPUS_SCHEMA = "multi-history-rag-v1"
INDEX_KINDS = ("chunks", "evidence_atoms", "context_chunks")


def _canonical_sha256(value: dict) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _area(box: list[float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersection_area(left: list[float], right: list[float]) -> float:
    return max(0.0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0.0, min(left[3], right[3]) - max(left[1], right[1]))


def _same_evidence_box(candidate: dict, evidence: dict, *, threshold: float) -> bool:
    gold_area = _area(evidence["bbox"])
    return bool(
        candidate["source_name"] == evidence["source_id"]
        and candidate["page"] == evidence["page"]
        and gold_area > 0
        and any(_intersection_area(box, evidence["bbox"]) / gold_area >= threshold
                for box in candidate.get("bboxes", [candidate["bbox"]]))
    )


def _rank_key(item: dict) -> tuple[str, int, str]:
    return item["source_name"], item["page"], _norm_text(item["text"])


def _percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sorted(values)[max(0, math.ceil(0.95 * len(values)) - 1)], 3)


def _evaluate_method(name: str, corpus_rows: list[dict], questions: list[dict],
                     rankings: dict[str, list[dict]], *, threshold: float,
                     latency_ms: list[float], **extra: object) -> dict:
    count = len(questions)
    hits1 = hits3 = complete3 = mappable = 0
    mapped_hits1 = mapped_hits3 = 0
    reciprocal: list[float] = []
    mapped_reciprocal: list[float] = []
    for question in questions:
        primary = [item for item in question["evidence"] if item["role"] == "primary"]
        question_mappable = bool(primary) and all(
            any(_same_evidence_box(row, item, threshold=threshold) for row in corpus_rows)
            for item in primary)
        mappable += int(question_mappable)
        ranked = rankings[question["id"]]
        hit_ranks = [i for i, candidate in enumerate(ranked, 1) if any(
            _same_evidence_box(candidate, item, threshold=threshold) for item in primary)]
        hits1 += int(1 in hit_ranks)
        hits3 += int(bool(hit_ranks))
        if question_mappable:
            mapped_hits1 += int(1 in hit_ranks)
            mapped_hits3 += int(bool(hit_ranks))
            mapped_reciprocal.append(1 / min(hit_ranks) if hit_ranks else 0.0)
        complete3 += int(bool(primary) and all(any(
            _same_evidence_box(candidate, item, threshold=threshold) for candidate in ranked)
            for item in primary))
        reciprocal.append(1 / min(hit_ranks) if hit_ranks else 0.0)
    return {
        "method": name,
        "candidate_count": len(corpus_rows),
        "question_count": count,
        "bbox_mappable_questions": mappable,
        "recall_1_all_questions": round(hits1 / count, 4) if count else 0.0,
        "recall_3_all_questions": round(hits3 / count, 4) if count else 0.0,
        "mrr_3_all_questions": round(sum(reciprocal) / count, 4) if count else 0.0,
        "recall_1_bbox_mappable_only": round(mapped_hits1 / mappable, 4) if mappable else 0.0,
        "recall_3_bbox_mappable_only": round(mapped_hits3 / mappable, 4) if mappable else 0.0,
        "mrr_3_bbox_mappable_only": round(sum(mapped_reciprocal) / mappable, 4) if mappable else 0.0,
        "complete_primary_bundle_at_3": round(complete3 / count, 4) if count else 0.0,
        "latency_ms_p50": round(median(latency_ms), 3) if latency_ms else None,
        "latency_ms_p95": _percentile95(latency_ms),
        **extra,
    }


def build(pack: dict, corpus: dict, *, bbox_coverage: float = 0.8,
          candidate_limit: int = 3, rrf_pool_per_index: int = 20, rrf_k: int = 60) -> dict:
    if pack.get("schema") != PACK_SCHEMA or not pack.get("questions"):
        raise ValueError("Aktif AYT deneme paketi gerekli")
    if corpus.get("schema") != CORPUS_SCHEMA:
        raise ValueError("Çok kaynaklı Tarih corpus'u gerekli")
    if not 0 < bbox_coverage <= 1 or candidate_limit != 3:
        raise ValueError("BBox eşiği 0-1 arasında ve aday bütçesi top-3 olmalı")
    books = {book.get("source_name"): book for book in corpus.get("books", [])}
    pack_sources = {source["id"]: source["source_checksum"] for source in pack.get("sources", [])}
    for source_id, checksum in pack_sources.items():
        book = books.get(source_id)
        if not book or book.get("source_checksum") != checksum:
            raise ValueError("Deneme paketi ve corpus kaynak checksum'ı eşleşmiyor")

    questions = pack["questions"]
    if len({question.get("id") for question in questions}) != len(questions):
        raise ValueError("Soru kimlikleri benzersiz olmalı")
    for question in questions:
        if not isinstance(question.get("question"), str) or len(question.get("choices", [])) != 5:
            raise ValueError("Her soru kökü ve beş şıkkı taşımalı")
        for evidence in question.get("evidence", []):
            if pack_sources.get(evidence.get("source_id")) != evidence.get("source_checksum"):
                raise ValueError("Kanıt kaynağı paket checksum'ıyla eşleşmiyor")

    indexes: dict[str, list[dict]] = {}
    for kind in INDEX_KINDS:
        rows = []
        for book in corpus["books"]:
            for item in book.get("index", {}).get(kind, []):
                if not isinstance(item.get("text"), str) or not isinstance(item.get("bbox"), list):
                    continue
                rows.append({**item, "source_name": book["source_name"], "bboxes": [item["bbox"]]})
        if not rows:
            raise ValueError(f"Corpus indeks türü boş: {kind}")
        indexes[kind] = rows

    engines = {kind: PreparedBM25(rows) for kind, rows in indexes.items()}
    results = []
    query_modes = {
        "question_only": lambda question: question["question"],
        "question_plus_topic": lambda question: " ".join(
            part for part in (question["question"], question.get("topic", "")) if part),
        "question_plus_choices": lambda question: " ".join(
            [question["question"], *question["choices"]]),
        "question_topic_choices": lambda question: " ".join(
            [question["question"], question.get("topic", ""), *question["choices"]]),
    }
    for mode, make_query in query_modes.items():
        for kind in INDEX_KINDS:
            rankings, latencies = {}, []
            for question in questions:
                started = time.perf_counter()
                rankings[question["id"]] = engines[kind].rank(make_query(question), candidate_limit)
                latencies.append((time.perf_counter() - started) * 1000)
            results.append(_evaluate_method(
                f"{kind}:{mode}", indexes[kind], questions, rankings,
                threshold=bbox_coverage, latency_ms=latencies,
            ))

    # Fixed-budget ablations compare retrieval-unit fusion without changing
    # the student path. Exact duplicate text is deduplicated only by source/page.
    query = lambda question: " ".join([question["question"], *question["choices"]])
    per_index: dict[str, dict[str, list[dict]]] = {}
    per_index_latency: dict[str, dict[str, float]] = {}
    for kind in ("context_chunks", "evidence_atoms"):
        per_index[kind] = {}
        per_index_latency[kind] = {}
        for question in questions:
            started = time.perf_counter()
            per_index[kind][question["id"]] = engines[kind].rank(
                query(question), max(candidate_limit, rrf_pool_per_index))
            per_index_latency[kind][question["id"]] = (time.perf_counter() - started) * 1000
    methods: dict[str, tuple[list[dict], dict[str, list[dict]], dict]] = {}

    hybrid_rows = indexes["context_chunks"] + indexes["evidence_atoms"]
    raw_rankings, raw_latencies = {}, []
    hybrid_engine = PreparedBM25(hybrid_rows)
    for question in questions:
        started = time.perf_counter()
        raw_rankings[question["id"]] = hybrid_engine.rank(query(question), candidate_limit)
        raw_latencies.append((time.perf_counter() - started) * 1000)
    methods["hybrid_raw_top3"] = (hybrid_rows, raw_rankings, {"latency": raw_latencies})

    dedup_by_key: dict[tuple[str, int, str], dict] = {}
    duplicate_rows_removed = 0
    for row in hybrid_rows:
        key = _rank_key(row)
        if key in dedup_by_key:
            dedup_by_key[key]["bboxes"].extend(row["bboxes"])
            duplicate_rows_removed += 1
        else:
            dedup_by_key[key] = {**row, "bboxes": list(row["bboxes"])}
    dedup_rows = list(dedup_by_key.values())
    dedup_engine = PreparedBM25(dedup_rows)
    dedup_rankings, dedup_latencies = {}, []
    for question in questions:
        started = time.perf_counter()
        dedup_rankings[question["id"]] = dedup_engine.rank(query(question), candidate_limit)
        dedup_latencies.append((time.perf_counter() - started) * 1000)
    methods["hybrid_exact_text_dedup_top3"] = (
        dedup_rows, dedup_rankings,
        {"latency": dedup_latencies, "duplicate_rows_removed": duplicate_rows_removed})

    for atom_count, context_count, name in (
        (1, 2, "quota_atom1_context2"), (2, 1, "quota_atom2_context1")):
        rankings, latencies = {}, []
        for question in questions:
            started = time.perf_counter()
            chosen = (per_index["evidence_atoms"][question["id"]][:atom_count]
                      + per_index["context_chunks"][question["id"]][:context_count])
            unique, seen = [], set()
            for row in chosen:
                if _rank_key(row) not in seen:
                    unique.append(row)
                    seen.add(_rank_key(row))
            rankings[question["id"]] = unique[:candidate_limit]
            selection_ms = (time.perf_counter() - started) * 1000
            latencies.append(
                per_index_latency["evidence_atoms"][question["id"]]
                + per_index_latency["context_chunks"][question["id"]]
                + selection_ms)
        methods[name] = (hybrid_rows, rankings, {"latency": latencies})

    rrf_rankings, rrf_latencies = {}, []
    for question in questions:
        started = time.perf_counter()
        pooled: dict[tuple[str, int, str], dict] = {}
        for kind in ("context_chunks", "evidence_atoms"):
            for rank, item in enumerate(per_index[kind][question["id"]], 1):
                key = _rank_key(item)
                if key not in pooled:
                    pooled[key] = {
                        "item": {**item, "bboxes": list(item["bboxes"])},
                        "score": 0.0,
                    }
                else:
                    record = pooled[key]
                    record["item"]["bboxes"].extend(item["bboxes"])
                record = pooled[key]
                record["score"] += 1 / (rrf_k + rank)
        ordered = sorted(pooled.values(), key=lambda value: (
            -value["score"], value["item"].get("page", 0), value["item"].get("id", "")))
        rrf_rankings[question["id"]] = [row["item"] for row in ordered[:candidate_limit]]
        fusion_ms = (time.perf_counter() - started) * 1000
        rrf_latencies.append(
            per_index_latency["context_chunks"][question["id"]]
            + per_index_latency["evidence_atoms"][question["id"]]
            + fusion_ms)
    methods[f"rrf_top{rrf_pool_per_index}_each_top3"] = (
        hybrid_rows, rrf_rankings, {"latency": rrf_latencies,
                                    "pool_per_index": rrf_pool_per_index, "rrf_k": rrf_k})

    for name, (rows, rankings, details) in methods.items():
        results.append(_evaluate_method(
            name, rows, questions, rankings, threshold=bbox_coverage,
            latency_ms=details.pop("latency"), **details,
        ))

    primary_evidence_count = sum(
        evidence.get("role") == "primary"
        for question in questions for evidence in question.get("evidence", []))
    return {
        "schema": SCHEMA,
        "active_pack_sha256": _canonical_sha256(pack),
        "corpus_checksum": corpus.get("corpus_checksum"),
        "source_checksums": {key: value for key, value in sorted(pack_sources.items())},
        "question_count": len(questions),
        "primary_evidence_count": primary_evidence_count,
        "bbox_coverage_threshold": bbox_coverage,
        "candidate_limit": candidate_limit,
        "runtime_environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "query_uses_answer_key_or_explanation": False,
        "gold_label_kind": "primary_evidence_bbox_localization_proxy",
        "human_relevance_labels": False,
        "runtime_enabled": False,
        "results": results,
        "notice": "Offline diagnostic only. Recall measures localization against pack source/page/bbox, not whether a chunk answers the question. Unmappable evidence is a miss in all-question metrics. No answer key, explanation, student response, or external service is used.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.pack), load(args.corpus))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"question_count": result["question_count"], "results": result["results"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
