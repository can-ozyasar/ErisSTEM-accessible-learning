"""Assemble partitioned answer-blind AI retrieval reviews without promotion.

The metrics answer only whether BM25's *own candidate set* contains an
AI-judged supporting atom.  They are not a blind relevance benchmark and are
never sufficient to choose a runtime retriever.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

SCHEMA = "ayt-history-provisional-bm25-ai-retrieval-assessment-v1"
REVIEW_SCHEMA = "deepseek-relation-retrieval-review-v1"


def build(baseline: dict, review_parts: list[dict]) -> dict:
    if baseline.get("schema") != "ayt-history-provisional-atom-bm25-baseline-v1" or baseline.get("k") != 3:
        raise ValueError("Top-3 provisional BM25 baseline gerekli")
    cases = {row.get("id"): row for row in baseline.get("cases", [])}
    if len(cases) != 24:
        raise ValueError("Tam 24 kilitli BM25 vakası gerekli")
    reviews: dict[str, dict] = {}
    for part in review_parts:
        if part.get("schema") != REVIEW_SCHEMA:
            raise ValueError("DeepSeek retrieval inceleme partisi gerekli")
        if (part.get("source_checksum") != baseline.get("candidate_checksum") or
                part.get("corpus_checksum") != baseline.get("corpus_checksum")):
            raise ValueError("İnceleme partisi baseline kaynak sürümüyle eşleşmiyor")
        if part.get("answer_key_accessed") is not False or part.get("worked_explanation_accessed") is not False:
            raise ValueError("Cevap anahtarı veya çözüm erişimli inceleme kabul edilmez")
        for review in part.get("reviews", []):
            identifier = review.get("candidate_id")
            if identifier in reviews:
                raise ValueError("Bir kilitli soru birden fazla kez incelenmiş")
            reviews[identifier] = review
    if set(reviews) != set(cases):
        raise ValueError("İnceleme partileri 24 kilitli soruyu tam bir kez kapsamalı")

    rows = []
    for identifier in sorted(cases):
        expected = cases[identifier].get("retrieved_atom_ids")
        review = reviews[identifier]
        judgments = {item.get("source_key"): item for item in review.get("judgments", [])}
        if not isinstance(expected, list) or len(expected) != 3 or set(judgments) != set(expected):
            raise ValueError("İnceleme kartları BM25 top-3 sıralamasıyla tam eşleşmeli")
        verdicts = [judgments[key].get("verdict") for key in expected]
        if any(verdict not in {"support", "wrong"} for verdict in verdicts):
            raise ValueError("İnceleme kart hükmü geçersiz")
        rows.append({"id": identifier, "question_diagnosis": review.get("question_diagnosis"),
                     "ranked_verdicts": verdicts,
                     "top_1_support": verdicts[0] == "support",
                     "top_3_any_support": "support" in verdicts,
                     "support_count": verdicts.count("support")})
    count = len(rows)
    diagnosis_counts = Counter(row["question_diagnosis"] for row in rows)
    result = {
        "schema": SCHEMA, "candidate_checksum": baseline["candidate_checksum"],
        "corpus_checksum": baseline["corpus_checksum"], "split_checksum": baseline.get("split_checksum"),
        "method": baseline.get("method"), "k": 3, "case_assessments": rows,
        "metrics": {
            "query_count": count,
            "ai_direct_evidence_rate": diagnosis_counts["direct_evidence_found"] / count,
            "ai_top_1_support_rate": sum(row["top_1_support"] for row in rows) / count,
            "ai_top_3_any_support_rate": sum(row["top_3_any_support"] for row in rows) / count,
            "ai_mean_support_cards_per_top_3": sum(row["support_count"] for row in rows) / count,
            "diagnoses": dict(sorted(diagnosis_counts.items())),
        },
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "student_data_accessed": False, "is_human_teacher_approval": False,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Provisional answer-blind AI assessment of BM25's own 24 candidate sets. It is not human/PDF approval, independent relevance gold, a dense/RRF comparison, or a runtime-retriever selection result.",
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True, action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.baseline), [load(path) for path in args.review])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
