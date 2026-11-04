"""Classify OGM AYT pages before OCR; answer and solution pages are excluded."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .ogm_ayt_source_manifest import _topic, parse_pages

SCHEMA = "ogm-ayt-page-classification-v1"
TEST_MARKER = re.compile(r"\b[1-4]\s*\.\s*test\b", re.IGNORECASE)
QUESTION_MARKER = re.compile(r"(?:^|\s)[0-9]{1,2}\s*\.\s+", re.IGNORECASE)


def classify(page: str) -> str:
    normalized = " ".join(page.casefold().split())
    if "cevap anahtarı" in normalized or "cevap anahtari" in normalized:
        return "answer_key"
    if "çözümlü sorular" in normalized or "çözüm:" in normalized:
        return "solved_or_explained"
    if TEST_MARKER.search(normalized):
        return "test_candidate"
    return "other"


def build(source: Path) -> dict:
    raw = source.read_bytes()
    pages = parse_pages(raw.decode("utf-8-sig"))
    rows = []
    for number, page in enumerate(pages, 1):
        topic = _topic(page)
        category = classify(page)
        rows.append({"page": number, "topic": topic, "category": category,
                     "question_marker_count": len(QUESTION_MARKER.findall(page)) if category == "test_candidate" else 0})
    # A test heading appears only on the first page of a multi-page block.
    # Continue that block through matching unheaded pages, then stop before a
    # worked-explanation or answer page.  Otherwise valid question pages are
    # silently treated as generic book content.
    active_topic = None
    for row in rows:
        if row["category"] in {"solved_or_explained", "answer_key"}:
            active_topic = None
        elif row["category"] == "test_candidate":
            active_topic = row["topic"]
        elif row["category"] == "other" and active_topic and row["topic"] == active_topic:
            row["category"] = "test_continuation"
    candidates = [row for row in rows if row["category"] in {"test_candidate", "test_continuation"} and row["topic"]]
    return {"schema": SCHEMA, "source_checksum": hashlib.sha256(raw).hexdigest(), "page_count": len(rows), "pages": rows,
            "summary": {"categories": dict(sorted(Counter(row["category"] for row in rows).items())),
                        "test_candidate_page_count": len(candidates),
                        "test_question_marker_count": sum(row["question_marker_count"] for row in candidates),
                        "test_pages_by_topic": dict(sorted(Counter(row["topic"] for row in candidates).items()))},
            "answer_key_exported": False, "solution_text_exported": False, "question_text_exported": False,
            "notice": "Private page classification only. Solved and answer-key pages are excluded before OCR and cannot become model-training examples."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
