"""Build a runtime AYT History pack only after complete human crop review.

The input candidate pack is deliberately not publishable.  This assembler
preserves its question wording and answer keys, binds every row to a completed
human PDF-crop review, and emits a separate checksum-bound runtime manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build(candidate: dict, sources: dict, split: dict, completed_review: dict, *, pack_id: str) -> dict:
    if candidate.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("özgün aday paketi gerekli")
    if sources.get("schema") != "ayt-history-meb-source-catalog-v1":
        raise ValueError("MEB kaynak kataloğu gerekli")
    if split.get("schema") != "ayt-history-candidate-split-v1":
        raise ValueError("dondurulmuş bölümleme gerekli")
    if completed_review.get("schema") != "ayt-history-human-pdf-crop-review-template-v1":
        raise ValueError("tamamlanmış insan PDF kırpımı incelemesi gerekli")
    questions = candidate.get("questions", [])
    if len(questions) != 120 or completed_review.get("candidate_checksum") != candidate.get("candidate_checksum"):
        raise ValueError("inceleme ve aday paketi aynı 120 soruya bağlı olmalı")
    if completed_review.get("question_set_checksum") != _digest(questions):
        raise ValueError("inceleme, aday soru metinleriyle uyuşmuyor")

    split_by_id = {item.get("id"): item.get("split") for item in split.get("records", [])}
    question_by_id = {item.get("id"): item for item in questions}
    review_by_id = {item.get("id"): item for item in completed_review.get("reviews", [])}
    if set(split_by_id) != set(question_by_id) or set(review_by_id) != set(question_by_id):
        raise ValueError("inceleme, bölümleme ve aday kimlikleri birebir eşleşmeli")
    expected_splits = {"development": 72, "retrieval_test": 24, "system_acceptance": 24}
    if Counter(split_by_id.values()) != expected_splits:
        raise ValueError("dondurulmuş bölümleme 72/24/24 olmalı")

    source_by_id = {item.get("id"): item for item in sources.get("sources", [])}
    output_questions = []
    used_source_ids: set[str] = set()
    for identifier, question in question_by_id.items():
        review = review_by_id[identifier]
        checks = review.get("checks", {})
        if (review.get("status") != "human_approved" or not isinstance(review.get("reviewer"), str)
                or not review["reviewer"].strip() or any(checks.get(key) is not True for key in (
                    "question_choices_match", "correct_label_grounded", "explanation_grounded",
                    "spoken_text_checked", "text_only_accessible"))):
            raise ValueError(f"insan PDF kırpımı onayı eksik: {identifier}")
        if review.get("question_checksum") != _digest(question):
            raise ValueError(f"inceleme soru metniyle uyuşmuyor: {identifier}")
        evidence = question.get("source_evidence")
        source = source_by_id.get(evidence.get("source_id") if isinstance(evidence, dict) else None)
        if not isinstance(evidence, dict) or source is None or source.get("source_checksum") != evidence.get("source_checksum"):
            raise ValueError(f"MEB kanıt kataloğunda yok: {identifier}")
        used_source_ids.add(source["id"])
        section = evidence.get("section_title") or "AYT Tarih"
        output_questions.append({
            "id": identifier,
            "authorship": "original",
            "review_method": "human_pdf_crop_review",
            "review_artifact_checksum": _digest(review),
            "topic": section,
            "outcome": f"MEB kaynak bilgisini yorumlama: {section}",
            "split": split_by_id[identifier],
            "question": question.get("question"),
            "spoken_question": question.get("spoken_question"),
            "choices": question.get("choices"),
            "correct_label": question.get("correct_label"),
            "explanation": question.get("explanation"),
            "evidence": [{
                "source_checksum": evidence.get("source_checksum"), "page": evidence.get("page"),
                "bbox": evidence.get("bbox"), "source_id": evidence.get("source_id"),
                "source_kind": "meb_textbook", "quote": evidence.get("quote"), "role": "primary",
            }],
            "visual_dependency": False,
            "visual_description_reviewed": False,
            "status": "approved",
        })
    return {"schema": "ayt-history-exam-pack-v1", "pack_id": pack_id,
            "sources": [source_by_id[source_id] for source_id in sorted(used_source_ids)],
            "questions": output_questions,
            "provenance": {"candidate_checksum": candidate.get("candidate_checksum"),
                           "split_checksum": _digest(split), "human_review_checksum": _digest(completed_review)},
            "runtime_enabled": False,
            "notice": "Local pilot package. It has completed human PDF-crop checks; it does not imply teacher equivalence or public distribution permission."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--completed-review", type=Path, required=True)
    parser.add_argument("--pack-id", default="ayt-tarih-local-pilot-v1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.candidate), load(args.sources), load(args.split), load(args.completed_review), pack_id=args.pack_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"question_count": len(result["questions"]), "runtime_enabled": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
