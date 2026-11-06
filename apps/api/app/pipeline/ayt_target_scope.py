"""Freeze the first AYT coach scope without carrying exam questions or answers.

The reviewed 2022--2026 sample establishes the grade.  It contains too few
distinct 12th-grade headings to choose six fine-grained sections honestly.
For that second step this module uses the OGM AYT EA 2018--2026 distribution
table, whose rows are explicitly bound to the installed 12th-grade textbook.
The resulting manifest is metadata only and is deliberately unsuitable as an
approval for RAG, runtime or QLoRA.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "ayt-target-scope-manifest-v1"

# Transcribed from the table on physical PDF pages 87--88, then bound below to
# exact section ids from the private MEB source index.  Keeping this compact
# metadata here makes the selection reproducible while keeping question text,
# options and answers out of the repository and output manifest.
EA_2018_2026_TARGETS = (
    ("2.1", "Millî Mücadele’ye Hazırlık Dönemi", 9),
    ("2.5", "Batı Cephesi ve Bu Cephede Öne Çıkan Şahsiyetler", 7),
    ("1.3", "I. Dünya Savaşı Sürecinde Osmanlı Devleti", 5),
    ("3.2", "Siyasi Alandaki Gelişmeler", 3),
    ("2.4", "Doğu ve Güney Cepheleri ile Bu Cephelerde Öne Çıkan Şahsiyetler", 2),
    ("3.1", "Atatürk İlkeleri", 2),
)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _grade12_book(corpus: dict) -> dict:
    books = [
        book
        for book in corpus.get("books", [])
        if book.get("grade") == 12 and book.get("source_name") == "inkilap-12-aday-eba.pdf"
    ]
    if len(books) != 1:
        raise ValueError("Hedef 12. sınıf MEB kitabı corpus içinde tek olmalı")
    return books[0]


def build(scope_report: dict, corpus: dict, distribution_pdf_checksum: str) -> dict:
    """Create a checksum-bound, content-free target-scope manifest."""
    if scope_report.get("schema") != "yks-history-scope-report-v1":
        raise ValueError("İncelenmiş AYT kapsam raporu gerekli")
    if scope_report.get("chosen_grade") != 12:
        raise ValueError("Resmî inceleme ilk kapsam için 12. sınıfı seçmemiş")
    if not distribution_pdf_checksum or len(distribution_pdf_checksum) != 64:
        raise ValueError("Dağılım PDF checksum değeri geçersiz")
    book = _grade12_book(corpus)
    sections = {section["id"]: section for section in book["index"].get("sections", [])}
    chunks = book["index"].get("chunks", [])
    rows = []
    for section_id, table_topic, question_count in EA_2018_2026_TARGETS:
        section = sections.get(section_id)
        if section is None:
            raise ValueError(f"MEB bölüm eşlemesi bulunamadı: {section_id}")
        candidate_count = sum(chunk.get("section_id") == section_id for chunk in chunks)
        if not candidate_count:
            raise ValueError(f"Kanıt adayı olmayan hedef bölüm: {section_id}")
        rows.append(
            {
                "section_id": section_id,
                "meb_section_title": section["title"],
                "distribution_table_topic": table_topic,
                "official_ea_2018_2026_question_count": question_count,
                "book_page_range": {"start": section["start"], "end": section["end"]},
                "candidate_context_count": candidate_count,
            }
        )
    counts = [row["official_ea_2018_2026_question_count"] for row in rows]
    if len(rows) != 6 or len({row["section_id"] for row in rows}) != 6 or min(counts) < 1:
        raise ValueError("Tam altı, farklı ve sınav dağılımında görülen bölüm gerekli")
    grade12_tags = [row for row in scope_report.get("unit_ranking", [])]
    return {
        "schema": SCHEMA,
        "selection_status": "locked_for_private_evidence_discovery",
        "grade": 12,
        "sections": rows,
        "selection_basis": {
            "grade_selection": {
                "method": "2022-2026 bağımsız incelenmiş AYT EA/SÖZ kapsam metadata'sı",
                "approved_tag_count": scope_report.get("approved_tag_count"),
                "chosen_grade": 12,
                "reviewed_unit_signal": grade12_tags,
            },
            "section_selection": {
                "method": "OGM AYT EA 2018-2026 ünite ve konu dağılım tablosunda en yüksek altı 12. sınıf konu satırı",
                "distribution_pdf_physical_pages": [87, 88],
                "distribution_pdf_checksum": distribution_pdf_checksum,
                "selection_counts": {
                    row["section_id"]: row["official_ea_2018_2026_question_count"] for row in rows
                },
            },
        },
        "source_binding": {
            "corpus_checksum": corpus.get("corpus_checksum"),
            "meb_source_name": book["source_name"],
            "meb_source_checksum": book["source_checksum"],
            "meb_index_checksum": book["index_checksum"],
            "scope_report_checksum": _digest(scope_report),
        },
        "target_question_count": 120,
        "target_examples": 720,
        "collection_strategy": "Her bölüm için önce 8 kaynak-kapsam kalibrasyon sorusu; kalite kapısı geçerse dengeli biçimde 20 soruya genişletilir.",
        "gates": {
            "question_transcription_review_required": True,
            "pdf_crop_source_review_required": True,
            "student_runtime_enabled": False,
            "qlora_enabled": False,
            "answer_key_accessed": False,
            "worked_explanation_accessed": False,
        },
        "notice": "Bu manifest yalnız private kaynak keşfi için bölüm allowlist'idir. Kaynak onayı, öğrenci RAG'ı, çalışma zamanı veya QLoRA eğitimi onayı değildir.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope-report", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--distribution-pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(
        json.loads(args.scope_report.read_text(encoding="utf-8")),
        json.loads(args.corpus.read_text(encoding="utf-8")),
        hashlib.sha256(args.distribution_pdf.read_bytes()).hexdigest(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"sections": len(result["sections"]), "status": result["selection_status"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
