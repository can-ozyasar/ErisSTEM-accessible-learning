"""Build a private, structurally safe question-review queue for tutor data.

The artifact intentionally contains identifiers and structural metadata only.
Question text, choices and answer information stay in the local source PDF and
the teacher review application.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from ..question_bank_extract import extract_book
from ..question_scope import AccessibilityAndScopeFilter

SCHEMA = "history-tutor-question-queue-v1"


def _topic(context: dict) -> str:
    value = unicodedata.normalize("NFKC", str(context.get("topic") or "Başlık eşleşmedi"))
    value = value.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", value).strip()


def _eligibility(candidate: dict, topic: str) -> list[str]:
    question, issues = candidate["question"], list(candidate.get("issues", []))
    blockers = list(issues)
    scope = AccessibilityAndScopeFilter().evaluate(question, issues=issues)
    if any(reason in {"embedded_visual", "referenced_visual", "structured_table"}
           for reason in scope.reasons):
        blockers.append("görsel_betimleme_gerekli")
    if question.get("question_type") != "multiple_choice" and "fill_in_the_blank" not in scope.format_tags:
        blockers.append("multiple_choice_değil")
    if topic == "Başlık eşleşmedi":
        blockers.append("konu_başlığı_yok")
    if topic.casefold() in {"ünite tarama testi", "tarama testi"}:
        blockers.append("konu_başlığı_yetersiz")
    return sorted(set(blockers))


def build(book: dict, target: int = 120) -> dict:
    if target < 1 or target > 120:
        raise ValueError("Hedef soru sayısı 1 ile 120 arasında olmalı")
    checksum = book.get("source_checksum")
    if not isinstance(checksum, str) or len(checksum) != 64:
        raise ValueError("Soru bankası checksum'ı geçersiz")
    by_topic: dict[str, list[dict]] = defaultdict(list)
    blocked: Counter[str] = Counter()
    for candidate in book.get("questions", []):
        question = candidate.get("question", {})
        source = question.get("source", {})
        page = source.get("page")
        context = book.get("page_contexts", {}).get(page) or book.get("page_contexts", {}).get(str(page), {})
        topic = _topic(context)
        blockers = _eligibility(candidate, topic)
        if blockers:
            blocked.update(blockers)
            continue
        by_topic[topic].append({
            "question_id": question["id"], "page": page, "number": question["number"],
            "topic": topic, "test_name": context.get("test_name"), "test_number": context.get("test_number"),
            "source_checksum": checksum,
        })
    for rows in by_topic.values():
        rows.sort(key=lambda row: (row["test_number"] is None, row["test_number"] or 0, row["page"], row["number"], row["question_id"]))
    selected: list[dict] = []
    while by_topic and len(selected) < target:
        for topic in sorted(by_topic):
            rows = by_topic[topic]
            if rows and len(selected) < target:
                selected.append(rows.pop(0))
            if not rows:
                del by_topic[topic]
    selected_ids = [row["question_id"] for row in selected]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("Soru kuyruğunda yinelenen kimlik oluştu")
    return {
        "schema": SCHEMA, "source_checksum": checksum, "target": target,
        "selected_count": len(selected), "selected": selected,
        "summary": {
            "all_candidate_count": len(book.get("questions", [])), "structurally_eligible_count": len(selected) + sum(len(rows) for rows in by_topic.values()),
            "selected_by_topic": dict(sorted(Counter(row["topic"] for row in selected).items())),
            "blocked_reasons": dict(sorted(blocked.items())),
            "needs_more_source_questions": len(selected) < target,
        },
        "answer_key_accessed": False, "question_text_exported": False, "student_data_accessed": False,
        "notice": "Private structural queue only. Selection is not question approval, evidence approval, graph approval or QLoRA eligibility.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", type=int, default=120)
    args = parser.parse_args()
    source_checksum = hashlib.sha256(args.source.read_bytes()).hexdigest()
    book = extract_book(args.source)
    if source_checksum != book["source_checksum"]:
        raise ValueError("Soru bankası checksum doğrulanamadı")
    result = build(book, args.target)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
