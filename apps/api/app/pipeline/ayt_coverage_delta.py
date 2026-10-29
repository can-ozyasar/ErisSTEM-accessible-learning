"""Compare two private AYT evidence-proposal runs without approving evidence.

The tool is deliberately metadata-only: it records ranks, book grades and
checksum-bound chunk identifiers.  It neither copies exam text nor treats a
newly retrieved candidate as a usable student source.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _by_id(proposals: dict) -> dict[str, dict]:
    return {row["candidate_id"]: row for row in proposals.get("proposals", [])}


def _summary(candidate: dict | None) -> dict | None:
    if not candidate:
        return None
    return {
        "chunk_id": candidate["chunk_id"],
        "source_checksum": candidate["source_checksum"],
        "grade": candidate["grade"],
        "page": candidate["page"],
    }


def _same_candidate(left: dict | None, right: dict | None) -> bool:
    return _summary(left) == _summary(right)


def build(baseline: dict, coverage: dict) -> dict:
    """Build a review-only difference report for two proposal manifests."""
    if baseline.get("schema") != "ayt-evidence-proposals-v1":
        raise ValueError("Beklenen temel öneri şeması bulunamadı")
    if coverage.get("schema") != "ayt-evidence-proposals-v1":
        raise ValueError("Beklenen kapsama öneri şeması bulunamadı")
    if baseline.get("question_source_checksum") != coverage.get("question_source_checksum"):
        raise ValueError("Farklı soru kaynakları karşılaştırılamaz")

    baseline_rows = _by_id(baseline)
    coverage_rows = _by_id(coverage)
    if set(baseline_rows) != set(coverage_rows):
        raise ValueError("Öneri çalıştırmalarındaki soru kümeleri eşleşmiyor")

    rows = []
    for candidate_id in sorted(baseline_rows):
        before, after = baseline_rows[candidate_id], coverage_rows[candidate_id]
        if before["status"] != "teacher_review_required":
            continue
        if after["status"] != "teacher_review_required":
            raise ValueError("Kapsama çalışması bağlı bir soruda öneriyi kaybetti")
        before_top = before.get("suggestions", [None])[0]
        after_top = after.get("suggestions", [None])[0]
        grade9_ranks = [
            index for index, suggestion in enumerate(after.get("suggestions", []), start=1)
            if suggestion.get("grade") == 9
        ]
        rows.append({
            "candidate_id": candidate_id,
            "exam_year": before.get("exam_year"),
            "top1_changed": not _same_candidate(before_top, after_top),
            "baseline_top1": _summary(before_top),
            "coverage_top1": _summary(after_top),
            "grade9_candidate_ranks": grade9_ranks,
            "grade9_in_top3": any(rank <= 3 for rank in grade9_ranks),
        })

    return {
        "schema": "ayt-evidence-coverage-delta-v1",
        "question_source_checksum": baseline["question_source_checksum"],
        "baseline_corpus_checksum": baseline["corpus_checksum"],
        "coverage_corpus_checksum": coverage["corpus_checksum"],
        "bound_question_count": len(rows),
        "top1_changed_count": sum(row["top1_changed"] for row in rows),
        "grade9_top3_count": sum(row["grade9_in_top3"] for row in rows),
        "rows": rows,
        "notice": (
            "Private retrieval-difference report. A grade-9 candidate is not evidence and "
            "may not be used by student RAG, evaluation gold data or QLoRA until its PDF crop "
            "is checked and a teacher assigns an approved source role."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(
        json.loads(args.baseline.read_text(encoding="utf-8")),
        json.loads(args.coverage.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
