"""Lock a private, answer-free AYT pilot pool to reviewed curriculum scope.

This module intentionally selects only pages already classified as test pages.
It does not parse solutions or answer keys, and its result is a page allowlist
rather than a claim that OCR has recovered every question correctly.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

SCHEMA = "ogm-ayt-pilot-pool-scope-v1"

# The first pilot is deliberately one coherent 12th-grade sequence.  These
# titles map to the installed 12th-grade MEB book and cover the history
# relationships most suitable for evidence bundles: event--date, cause--
# effect, chronology and person--event.
DEFAULT_TOPICS = (
    "Millî Mücadele",
    "Atatürkçülük ve Türk İnkılabı",
    "İki Savaş Arasındaki Dönemde Türkiye ve Dünya",
    "II. Dünya Savaşı Sürecinde Türkiye ve Dünya",
    "II. Dünya Savaşı Sonrasında Türkiye ve Dünya",
    "21. Yüzyılın Eşiğinde Türkiye ve Dünya",
)


def build(classification: dict, topics: tuple[str, ...] = DEFAULT_TOPICS) -> dict:
    if classification.get("schema") != "ogm-ayt-page-classification-v1":
        raise ValueError("OGM sayfa sınıflandırma şeması geçersiz")
    if len(topics) != 6 or len(set(topics)) != 6:
        raise ValueError("Pilot kapsamı tam altı farklı ünite içermeli")

    pages_by_topic: dict[str, list[int]] = defaultdict(list)
    for row in classification.get("pages", []):
        if row.get("category") in {"test_candidate", "test_continuation"} and row.get("topic") in topics:
            pages_by_topic[row["topic"]].append(row["page"])
    missing = [topic for topic in topics if not pages_by_topic[topic]]
    if missing:
        raise ValueError(f"Test sayfası bulunmayan üniteler: {', '.join(missing)}")

    units = [{"topic": topic, "test_pages": sorted(pages_by_topic[topic])} for topic in topics]
    pages = [page for unit in units for page in unit["test_pages"]]
    return {
        "schema": SCHEMA,
        "source_checksum": classification["source_checksum"],
        "grade": 12,
        "units": units,
        "page_allowlist": sorted(pages),
        "page_count": len(pages),
        "target_candidate_count": 120,
        "scope_status": "locked_for_private_extraction",
        "selection_basis": {
            "official_exam_window": "2022-2026 AYT Tarih pilot",
            "curriculum_alignment": "12. sınıf MEB İnkılap Tarihi ve Atatürkçülük",
            "review_requirement": "Resmî soru etiketi ve MEB PDF kesiti incelemesi olmadan soru ya da kanıt runtime/QLoRA'ya girmez.",
        },
        "answer_key_accessed": False,
        "solution_text_exported": False,
        "student_runtime_enabled": False,
        "notice": "Private extraction allowlist. The target count is a collection target, not an OCR acceptance claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classification", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--topics", help="Virgülle ayrılmış altı OGM ünite başlığı")
    args = parser.parse_args()
    topics = tuple(item.strip() for item in args.topics.split(",")) if args.topics else DEFAULT_TOPICS
    result = build(json.loads(args.classification.read_text(encoding="utf-8")), topics)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
