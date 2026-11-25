"""Prepare a safer second retrieval pass for OGM questions that abstained.

This is deliberately an answer-free retrieval challenger.  It never consults
the answer key and cannot enable a runtime question.  A later independent
PDF/evidence review must still establish full claim coverage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from ..history_rag import PreparedBM25
from .prepare_ogm_real_question_evidence_queue import _diverse, _documents


SCHEMA = "ogm-ayt-real-question-evidence-queue-v1"


def _checksum(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _question_text(question: dict, *, include_choices: bool) -> str:
    parts = [part.get("text", "").strip() for part in question.get("parts", [])]
    if include_choices:
        parts.extend(choice.get("text", "").strip() for choice in question.get("choices", []))
    return " ".join(item for item in parts if item)


def _rrf(*rankings: list[dict], constant: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    documents: dict[str, dict] = {}
    for ranking in rankings:
        for position, document in enumerate(ranking, start=1):
            identifier = document["id"]
            documents[identifier] = document
            scores[identifier] = scores.get(identifier, 0.0) + 1 / (constant + position)
    return sorted(documents.values(), key=lambda item: (-scores[item["id"]], item["id"]))


def build(questions: dict, readiness: dict, corpus: dict, prior_review: dict, *, first_stage_limit: int = 36,
          candidate_limit: int = 12) -> dict:
    if questions.get("schema") != "ayt-target-question-candidates-v1":
        raise ValueError("gerçek soru aday paketi gerekli")
    if readiness.get("schema") != "ogm-ayt-real-question-pilot-readiness-v1":
        raise ValueError("onaylı gerçek soru hazırlık raporu gerekli")
    if prior_review.get("schema") != "ogm-ayt-real-question-evidence-pdf-review-v1":
        raise ValueError("önceki kanıt denetimi gerekli")
    if not 1 <= candidate_limit <= first_stage_limit:
        raise ValueError("retrieval aday sınırları geçersiz")
    question_checksum = questions.get("source_checksum")
    if (readiness.get("source_checksum") != question_checksum
            or prior_review.get("question_source_checksum") != question_checksum):
        raise ValueError("soru, hazırlık ve önceki inceleme checksum değerleri uyuşmuyor")
    if prior_review.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("önceki inceleme ile MEB corpus sürümü uyuşmuyor")
    allowed = {row["id"] for row in readiness.get("approved_transcription_candidates", [])}
    source_rows = {row["candidate_id"]: row for row in questions.get("rows", [])}
    review_rows = {row.get("candidate_id"): row for row in prior_review.get("reviews", [])}
    abstained = [identifier for identifier, review in review_rows.items()
                 if review.get("status") == "ai_consensus_abstain"]
    if not abstained:
        raise ValueError("iyileştirme için çekimser kalınmış soru bulunamadı")
    if any(identifier not in allowed or identifier not in source_rows for identifier in abstained):
        raise ValueError("çekimser soru doğrulanmış transkripsiyon havuzunda değil")
    documents = _documents(corpus)
    index = PreparedBM25(documents)
    proposals = []
    for identifier in sorted(abstained):
        row = source_rows[identifier]
        question = row["question"]
        stem_query = _question_text(question, include_choices=False)
        full_query = _question_text(question, include_choices=True)
        if not stem_query or len(question.get("choices", [])) != 5:
            raise ValueError(f"soru kökü veya şıklar bozuk: {identifier}")
        started = time.perf_counter()
        stem_ranked = index.rank(stem_query, first_stage_limit)
        full_ranked = index.rank(full_query, first_stage_limit)
        selected = _diverse(_rrf(stem_ranked, full_ranked), candidate_limit)
        proposals.append({
            "candidate_id": identifier,
            "deneme_number": row["deneme_number"],
            "question_number": question["number"],
            "question_text": full_query,
            "status": "challenger_candidates_require_independent_pdf_crop_review" if selected else "insufficient_candidate_set",
            "retrieval_ms": round((time.perf_counter() - started) * 1000, 3),
            "suggestions": selected,
        })
    return {
        "schema": SCHEMA,
        "question_source_checksum": question_checksum,
        "corpus_checksum": corpus["corpus_checksum"],
        "question_count": len(proposals),
        "retrieval": {
            "method": "bm25_rrf_stem_and_full_question_challenger",
            "first_stage_limit_per_query": first_stage_limit,
            "candidate_limit": candidate_limit,
            "rrf_constant": 60,
            "answer_key_used": False,
            "supplementary_source_used": False,
        },
        "parent_review_checksum": _checksum(prior_review),
        "proposals": proposals,
        "runtime_enabled": False,
        "notice": (
            "Second-pass candidates for previously abstained questions only. They are answer-free and require "
            "an independent full-coverage PDF review before any pilot-package decision."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--prior-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    report = build(load(args.questions), load(args.readiness), load(args.corpus), load(args.prior_review))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"questions": report["question_count"], "runtime_enabled": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
