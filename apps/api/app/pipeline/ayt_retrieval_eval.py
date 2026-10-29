"""Private gold-evidence workflow and retrieval metrics for the AYT pilot.

This module records teacher judgments before comparing retrievers.  It neither
approves passages nor invokes a language model.  The resulting artifact stays
in the private workspace and is the gate for dense/hybrid experiments.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from ..history_rag import rank_chunks
from .ayt_evidence_match import _lesson_prose_candidates, _question_text

ROLES = {"primary", "context", "relation", "contrast"}
ROLE_GAIN = {"primary": 3, "relation": 2, "context": 2, "contrast": 1}
OUTCOMES = {"pending", "evidence_selected", "reretrieve", "insufficient"}


def _source_key(source_checksum: str, chunk_id: str) -> str:
    return f"{source_checksum}:{chunk_id}"


def build_template(questions: dict, proposals: dict) -> dict:
    """Create a teacher-fillable judgment template from private suggestions."""
    if questions.get("source_checksum") != proposals.get("question_source_checksum"):
        raise ValueError("Soru ve öneri checksum'ları eşleşmiyor")
    cases = []
    for proposal in proposals.get("proposals", []):
        if proposal.get("status") != "teacher_review_required":
            continue
        candidates = [{
            "source_key": _source_key(item["source_checksum"], item["chunk_id"]),
            "source_checksum": item["source_checksum"], "chunk_id": item["chunk_id"],
            "grade": item["grade"], "page": item["page"], "section_title": item["section_title"],
            "role": None,
        } for item in proposal.get("suggestions", [])]
        cases.append({
            "candidate_id": proposal["candidate_id"], "exam_year": proposal["exam_year"],
            "outcome": "pending", "crop_checked": False, "reviewer": None,
            "judgments": candidates, "note": None,
        })
    return {
        "schema": "ayt-retrieval-gold-v1", "corpus_checksum": proposals["corpus_checksum"],
        "question_source_checksum": questions["source_checksum"], "cases": cases,
        "notice": (
            "Private teacher judgment template. Set role only after checking the PDF crop; "
            "this file does not approve a source for student RAG or QLoRA."
        ),
    }


def _validate_gold(gold: dict, proposals: dict) -> None:
    if gold.get("schema") != "ayt-retrieval-gold-v1":
        raise ValueError("Beklenen altın kanıt şeması bulunamadı")
    for key in ("corpus_checksum", "question_source_checksum"):
        if gold.get(key) != proposals.get(key if key == "corpus_checksum" else "question_source_checksum"):
            raise ValueError("Altın kanıt sürümü öneri sürümüyle eşleşmiyor")
    proposal_ids = {row["candidate_id"] for row in proposals.get("proposals", [])
                    if row.get("status") == "teacher_review_required"}
    observed = set()
    for case in gold.get("cases", []):
        identifier = case.get("candidate_id")
        if identifier not in proposal_ids or identifier in observed:
            raise ValueError("Altın kanıt soru kimliği geçersiz")
        observed.add(identifier)
        if case.get("outcome") not in OUTCOMES:
            raise ValueError("Altın kanıt sonucu geçersiz")
        roles = [item.get("role") for item in case.get("judgments", []) if item.get("role")]
        if any(role not in ROLES for role in roles):
            raise ValueError("Kanıt rolü geçersiz")
        if case.get("outcome") == "evidence_selected":
            if not case.get("crop_checked") or not case.get("reviewer") or "primary" not in roles:
                raise ValueError("Seçilen kanıt PDF kırpımı, inceleyen ve primary rolü gerektirir")
        elif roles:
            raise ValueError("Kanıt seçilmediyse rol atanamaz")


def _ranked_chunks(corpus: dict, query: str, limit: int) -> list[dict]:
    ranked = []
    for book in corpus.get("books", []):
        for item in rank_chunks(_lesson_prose_candidates(book), query, limit=limit):
            ranked.append({**item, "source_checksum": book["source_checksum"], "grade": book["grade"]})
    return sorted(ranked, key=lambda item: (-item["score"], item["grade"], item["page"], item["id"]))[:limit]


def _ndcg(retrieved: list[str], relevant: dict[str, int], k: int) -> float:
    dcg = sum((2 ** relevant.get(key, 0) - 1) / math.log2(position + 2)
              for position, key in enumerate(retrieved[:k]))
    ideal = sorted(relevant.values(), reverse=True)[:k]
    idcg = sum((2 ** gain - 1) / math.log2(position + 2) for position, gain in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def evaluate_bm25(gold: dict, questions: dict, proposals: dict, corpus: dict, limit: int = 3) -> dict:
    """Evaluate BM25 only on completed, source-checked pilot cases."""
    _validate_gold(gold, proposals)
    if corpus.get("corpus_checksum") != gold.get("corpus_checksum"):
        raise ValueError("Corpus checksum altın kanıtla eşleşmiyor")
    question_map = {row["candidate_id"]: row["question"] for row in questions.get("candidates", [])}
    complete = [case for case in gold.get("cases", []) if case.get("outcome") == "evidence_selected"]
    results = []
    for case in complete:
        relevant = {
            item["source_key"]: ROLE_GAIN[item["role"]]
            for item in case["judgments"] if item.get("role") in ROLE_GAIN
        }
        started = time.perf_counter()
        ranked = _ranked_chunks(corpus, _question_text(question_map[case["candidate_id"]]), limit)
        elapsed_ms = (time.perf_counter() - started) * 1000
        keys = [_source_key(item["source_checksum"], item["id"]) for item in ranked]
        first = next((position + 1 for position, key in enumerate(keys) if key in relevant), None)
        results.append({
            "candidate_id": case["candidate_id"], "retrieved": keys,
            "recall": len(set(keys) & set(relevant)) / len(relevant),
            "mrr": 1 / first if first else 0.0,
            "ndcg": _ndcg(keys, relevant, limit),
            "top1_wrong": bool(keys) and keys[0] not in relevant,
            "latency_ms": round(elapsed_ms, 3),
        })
    count = len(results)
    def mean(key: str) -> float:
        return round(sum(row[key] for row in results) / count, 4) if count else 0.0
    return {
        "schema": "ayt-retrieval-eval-v1", "method": "bm25_lesson_prose_only",
        "corpus_checksum": corpus["corpus_checksum"], "k": limit, "evaluated_cases": count,
        "summary": {
            "recall_at_k": mean("recall"), "mrr_at_k": mean("mrr"), "ndcg_at_k": mean("ndcg"),
            "top1_wrong_rate": mean("top1_wrong"), "mean_latency_ms": mean("latency_ms"),
            "pending_or_unusable_cases": len(gold.get("cases", [])) - count,
        }, "cases": results,
        "notice": "No conclusion until enough teacher-reviewed cases exist; metrics are reported separately.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    template = subparsers.add_parser("template")
    template.add_argument("--questions", type=Path, required=True)
    template.add_argument("--proposals", type=Path, required=True)
    template.add_argument("--output", type=Path, required=True)
    evaluate = subparsers.add_parser("evaluate-bm25")
    evaluate.add_argument("--gold", type=Path, required=True)
    evaluate.add_argument("--questions", type=Path, required=True)
    evaluate.add_argument("--proposals", type=Path, required=True)
    evaluate.add_argument("--corpus", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
    if args.command == "template":
        result = build_template(questions, proposals)
    else:
        result = evaluate_bm25(json.loads(args.gold.read_text(encoding="utf-8")), questions, proposals,
                               json.loads(args.corpus.read_text(encoding="utf-8")), args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
