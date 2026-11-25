"""Extract checksum-bound AYT Tarih-1 answers from the OGM deneme PDF itself."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf

SCHEMA = "ogm-ayt-history-answer-key-v1"
ANSWER_KEY_FIRST_PAGE = 415
ANSWER_PATTERN = re.compile(r"(?m)^\s*(\d{1,2})\.\s*([A-E])\s*$")


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_social_sciences_answers(text: str) -> dict[int, str]:
    pairs = [(int(number), choice) for number, choice in ANSWER_PATTERN.findall(text)]
    if len(pairs) < 80:
        raise ValueError("cevap anahtarı sayfasında iki adet 40 soruluk test bulunamadı")
    social = pairs[:40]
    if [number for number, _ in social] != list(range(1, 41)):
        raise ValueError("sosyal bilimler cevapları 1-40 sıralı değil")
    return dict(social)


def build(candidate: dict, source_pdf: Path) -> dict:
    if candidate.get("schema") != "ayt-target-question-candidates-v1":
        raise ValueError("AYT soru aday paketi gerekli")
    source_checksum = checksum(source_pdf)
    if source_checksum != candidate.get("source_checksum"):
        raise ValueError("cevap anahtarı PDF checksum'ı aday paketiyle uyuşmuyor")
    rows = candidate.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("soru adayları bulunamadı")
    by_deneme: dict[int, dict[int, str]] = {}
    with pymupdf.open(source_pdf) as document:
        for deneme_number in sorted({item.get("deneme_number") for item in rows if isinstance(item.get("deneme_number"), int)}):
            page_number = ANSWER_KEY_FIRST_PAGE + deneme_number - 1
            if page_number > document.page_count:
                raise ValueError(f"{deneme_number}. deneme için cevap anahtarı sayfası yok")
            by_deneme[deneme_number] = parse_social_sciences_answers(document[page_number - 1].get_text("text"))
    records = []
    for item in rows:
        question = item.get("question", {})
        deneme_number = item.get("deneme_number")
        question_number = question.get("number")
        if not isinstance(deneme_number, int) or not isinstance(question_number, int):
            continue
        if not 25 <= question_number <= 34:
            continue
        answer = by_deneme.get(deneme_number, {}).get(question_number)
        if answer is None:
            raise ValueError(f"{deneme_number}. deneme {question_number}. soru için cevap bulunamadı")
        records.append({
            "candidate_id": item["candidate_id"],
            "deneme_number": deneme_number,
            "question_number": question_number,
            "correct_choice": answer,
            "answer_key_source": {
                "source_name": source_pdf.name,
                "source_checksum": source_checksum,
                "page": ANSWER_KEY_FIRST_PAGE + deneme_number - 1,
                "section": "Türk Dili ve Edebiyatı - Sosyal Bilimler 1 Testi",
            },
        })
    if len(records) != len(rows):
        raise ValueError("tüm adaylar Tarih-1 25-34 soru aralığında değil")
    return {
        "schema": SCHEMA,
        "source_name": source_pdf.name,
        "source_checksum": source_checksum,
        "answer_key_pages": {str(key): ANSWER_KEY_FIRST_PAGE + key - 1 for key in by_deneme},
        "record_count": len(records),
        "records": records,
        "human_answer_key_review_required": True,
        "runtime_enabled": False,
        "notice": "Answers were parsed from the same checksum-bound OGM PDF. They remain review-only until joined with source evidence and a pilot package.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.candidate.read_text(encoding="utf-8")), args.source_pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"record_count": result["record_count"], "runtime_enabled": False}))


if __name__ == "__main__":
    main()
