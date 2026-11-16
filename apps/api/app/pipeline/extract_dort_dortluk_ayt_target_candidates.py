"""Private discovery of target-scope questions in OGM's Dört Dörtlük AYT Tarih.

Only explicitly allowlisted test pages are opened.  Worked examples and the
answer-key pages are never parsed by this pipeline.  Output remains private
and discovery-only; PDF crop review and teacher scope/evidence approval remain
required before any downstream use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

from ..question_bank_extract import extract_page
from ..question_scope import visual_dependency_reasons

SCHEMA = "ogm-dort-dortluk-ayt-target-candidates-v1"
SOURCE_NAME = "dort-dortluk-ayt-tarih.pdf"
EXPECTED_CHECKSUM = "9c94308aec664aca55be835bfb61f278b03eecc28e842c33fc44a615f903e683"

# Physical PDF pages, verified against printed page labels and test-page
# headers.  Page ranges contain test pages only; worked-question spreads are
# deliberately skipped.  Multi-section ranges stay unresolved for review.
PAGE_SCOPE = {
    "1.3": [(229, 235)],
    "2.1|2.4|2.5": [(239, 245)],
    "3.1": [(251, 257)],
    "3.2": [(261, 267)],
}


def _question_text(question: dict) -> str:
    return " ".join(part.get("text", "") for part in question.get("parts", []))


def _in_scope_page(page_number: int) -> str | None:
    for section_group, ranges in PAGE_SCOPE.items():
        if any(start <= page_number <= end for start, end in ranges):
            return section_group
    return None


def build(source: Path, scope_manifest: dict) -> dict:
    raw = source.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    if source.name != SOURCE_NAME or checksum != EXPECTED_CHECKSUM:
        raise ValueError("Dört Dörtlük PDF adı/checksum allowlist ile eşleşmiyor")
    if scope_manifest.get("schema") != "ayt-target-scope-manifest-v2":
        raise ValueError("Kilitli AYT hedef kapsam manifesti gerekli")
    target_ids = {row["section_id"] for row in scope_manifest.get("sections", [])}
    if set(PAGE_SCOPE) and not {"1.3", "2.1", "2.4", "2.5", "3.1", "3.2"} <= target_ids:
        raise ValueError("Kaynak kapsamı kilitli altı AYT bölümle uyumlu değil")

    rows: list[dict] = []
    review_rows: list[dict] = []
    excluded: list[dict] = []
    scanned_pages = []
    with pymupdf.open(stream=raw, filetype="pdf") as pdf:
        if len(pdf) != 315:
            raise ValueError("PDF sayfa sayısı beklenen kaynakla eşleşmiyor")
        for page_number in sorted({page for spans in PAGE_SCOPE.values()
                                   for start, end in spans for page in range(start, end + 1)}):
            page = pdf[page_number - 1]
            page_text = page.get_text("text")
            header = " ".join(page_text.splitlines()[:5]).casefold()
            range_start = next(start for spans in PAGE_SCOPE.values()
                               for start, end in spans if start <= page_number <= end)
            if ((page_number - range_start) % 2 == 0 and "test" not in header):
                raise ValueError(f"Test başlığı doğrulanamadı: {page_number}")
            if "çözümlü" in header or "cevap anahtarı" in header:
                raise ValueError(f"Allowlist sayfası test başlığı doğrulamasını geçemedi: {page_number}")
            # Validate printed page number; physical PDF pages have front matter
            # and therefore a stable +2 offset in these target spreads.
            printed_page = page_number - 2
            if str(printed_page) not in page_text[:100]:
                raise ValueError(f"Basılı sayfa eşleşmesi doğrulanamadı: {page_number}")
            scanned_pages.append(page_number)
            for item in extract_page(page, page_number, checksum):
                question = item["question"]
                issues = list(item.get("issues", []))
                group = _in_scope_page(page_number)
                if not group:
                    continue
                question_id = f"dort-dortluk:{checksum[:12]}:p{page_number}:q{question['number']}"
                reasons = visual_dependency_reasons(question, issues)
                if reasons:
                    excluded.append({"candidate_id": question_id, "page": page_number,
                                     "question_number": question["number"],
                                     "reason_codes": reasons,
                                     "status": "kapsam_disi_gorsel_bagimliligi"})
                    continue
                candidate = {
                    "candidate_id": question_id,
                    "source_kind": "ogm_dort_dortluk_ayt_tarih_private",
                    "source_name": source.name,
                    "source_checksum": checksum,
                    "source_physical_page": page_number,
                    "source_printed_page": printed_page,
                    "source_bbox": question["source"]["bbox"],
                    "page_scope_candidates": group.split("|"),
                    "question": question,
                    "extraction_issues": issues,
                    "transcription_status": "pdf_kirpimi_ogretmen_incelemesi_gerekli",
                    "target_scope_status": "sayfa_kapsami_adayi_ogretmen_dogrulamali",
                    "answer_key_accessed": False,
                    "worked_explanation_accessed": False,
                    "runtime_enabled": False,
                    "qlora_enabled": False,
                }
                (review_rows if issues or question.get("question_type") != "multiple_choice"
                 else rows).append(candidate)

    return {
        "schema": SCHEMA,
        "source_name": source.name,
        "source_checksum": checksum,
        "scope_manifest_version": scope_manifest.get("manifest_version"),
        "scope_manifest_checksum": hashlib.sha256(
            json.dumps(scope_manifest, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest(),
        "page_scope": PAGE_SCOPE,
        "scanned_test_pages": scanned_pages,
        "candidate_count": len(rows),
        "review_count": len(review_rows),
        "visual_exclusion_count": len(excluded),
        "rows": rows,
        "review_queue": review_rows,
        "visual_exclusions": excluded,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "student_rag_enabled": False,
        "kaggle_export_enabled": False,
        "qlora_enabled": False,
        "notice": "Özel keşif havuzu; soru kapsamı, metin ve kaynak kesiti öğretmen incelemesi olmadan onaylı değildir.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scope = json.loads(args.scope.read_text(encoding="utf-8"))
    result = build(args.source, scope)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "candidate_count", "review_count", "visual_exclusion_count", "scanned_test_pages",
        "answer_key_accessed", "worked_explanation_accessed")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
