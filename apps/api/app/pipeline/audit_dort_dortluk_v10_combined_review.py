"""Validate a blind combined evidence review against its private review pack."""
from __future__ import annotations

import argparse
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

DECISIONS = {"direct", "bounded_inference", "insufficient"}
SAFE_FALSE_FLAGS = (
    "answer_key_accessed", "worked_explanation_accessed", "teacher_approval",
    "runtime_enabled", "qlora_enabled", "kaggle_enabled",
)


def _norm(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def validate(review_input: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    if review_input.get("schema") != "dort-dortluk-v10-combined-support-review-input-v1":
        raise ValueError("Beklenmeyen birleşik inceleme paketi şeması")
    if report.get("schema") != "dort-dortluk-combined-support-agent-review-v1":
        raise ValueError("Beklenmeyen bağımsız inceleme şeması")
    for field in ("source_checksum", "corpus_checksum"):
        if review_input.get(field) != report.get(field):
            raise ValueError(f"{field} inceleme paketiyle eşleşmiyor")
    if review_input.get("review_scope") != "combined_candidate_evidence_only":
        raise ValueError("İnceleme girdisi birleşik aday kanıt kapsamı olmalı")
    if report.get("review_scope") != "research_only_combined_bundle_diagnostic":
        raise ValueError("İnceleme raporu araştırma tanılama kapsamı olmalı")
    for source in (review_input, report):
        for flag in SAFE_FALSE_FLAGS:
            if source.get(flag) is not False:
                raise ValueError(f"{flag} false olmalı; onay/ürün kullanımı kapalı kalmalı")

    expected_rows = {row.get("candidate_id"): row for row in review_input.get("rows", [])}
    reviewed_rows = {row.get("candidate_id"): row for row in report.get("rows", [])}
    if None in expected_rows or len(expected_rows) != len(review_input.get("rows", [])):
        raise ValueError("Girdi paketinde soru kimliği eksik veya yinelenmiş")
    if None in reviewed_rows or len(reviewed_rows) != len(report.get("rows", [])):
        raise ValueError("İnceleme raporunda soru kimliği eksik veya yinelenmiş")
    if set(expected_rows) != set(reviewed_rows):
        raise ValueError("İnceleme raporu soru kapsamı girdi paketiyle aynı değil")
    if review_input.get("question_count") != len(expected_rows):
        raise ValueError("Girdi soru sayısı uyuşmuyor")

    counts: Counter[str] = Counter()
    citation_count = 0
    checked_cards = 0
    indexed_ready_count = 0
    for candidate_id, review_row in reviewed_rows.items():
        source_row = expected_rows[candidate_id]
        if review_row.get("original_question_page_checked") is not True:
            raise ValueError(f"{candidate_id}: soru sayfası görsel olarak kontrol edilmemiş")
        if review_row.get("all_supplied_crops_checked") is not True:
            raise ValueError(f"{candidate_id}: tüm kanıt kesitleri kontrol edilmemiş")
        decision = review_row.get("decision")
        if decision not in DECISIONS:
            raise ValueError(f"{candidate_id}: geçersiz karar")
        counts[decision] += 1

        cards = {card["card_label"]: card for card in source_row.get("evidence_cards", [])}
        checked = review_row.get("evidence_cards_checked", [])
        checked_by_label = {card.get("card_label"): card for card in checked}
        if len(checked_by_label) != len(checked) or set(checked_by_label) != set(cards):
            raise ValueError(f"{candidate_id}: supplied evidence card coverage mismatch")
        if any(card.get("crop_checked") is not True for card in checked):
            raise ValueError(f"{candidate_id}: unverified evidence crop")
        checked_cards += len(checked)

        for citation in review_row.get("citations", []):
            label = citation.get("card_label")
            card = cards.get(label)
            if card is None or citation.get("chunk_id") != card.get("chunk_id"):
                raise ValueError(f"{candidate_id}: citation does not map to an input card")
            if citation.get("source_page") != card.get("source_page"):
                raise ValueError(f"{candidate_id}: citation page mismatch")
            quote = str(citation.get("exact_visible_quote", "")).strip()
            if not quote:
                raise ValueError(f"{candidate_id}: citation quote is empty")
            if citation.get("indexed_text_ready") is True:
                excerpt = str(card.get("indexed_excerpt", ""))
                if _norm(quote) not in _norm(excerpt):
                    raise ValueError(f"{candidate_id}: indexed-ready quote absent from indexed excerpt")
                if citation.get("source_text_alignment_issue") not in (None, ""):
                    raise ValueError(f"{candidate_id}: indexed-ready citation flags source mismatch")
                indexed_ready_count += 1
            citation_count += 1

        for card in checked:
            if card.get("cited") is True and not any(
                citation.get("card_label") == card.get("card_label")
                for citation in review_row.get("citations", [])
            ):
                raise ValueError(f"{candidate_id}: cited card has no citation record")

    declared = report.get("summary", {})
    if declared.get("decision_counts") != dict(sorted(counts.items())):
        raise ValueError("Karar sayımları rapor özetiyle uyuşmuyor")
    return {
        "schema": "dort-dortluk-v10-combined-support-review-validation-v1",
        "source_checksum": review_input.get("source_checksum"),
        "corpus_checksum": review_input.get("corpus_checksum"),
        "question_count": len(expected_rows),
        "decision_counts": dict(sorted(counts.items())),
        "evidence_cards_checked": checked_cards,
        "citations_checked": citation_count,
        "indexed_text_ready_citations": indexed_ready_count,
        "all_questions_and_cards_covered": True,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "teacher_approval": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "kaggle_enabled": False,
        "notice": "Selected partial-delta diagnostic only; not a corpus-wide retrieval metric or product approval.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(
        json.loads(args.input.read_text(encoding="utf-8")),
        json.loads(args.report.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
