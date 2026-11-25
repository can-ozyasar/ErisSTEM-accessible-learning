"""Verify that every candidate's quoted evidence is inside its local PDF crop."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import pymupdf

SCHEMA = "ayt-history-candidate-pdf-crop-text-audit-v1"


def _normalise(text: str) -> str:
    # PyMuPDF retains a soft hyphen followed by a physical line break.  It is
    # one word in the PDF, not evidence of a missing token.  Preserve real
    # punctuation/hyphens while joining only line-wrap markers.
    text = re.sub(r"(?:\u00ad|-)\s*\n\s*", "", text)
    text = re.sub(r"\u00ad\s*", "", text).replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip().casefold()


def _unicode_compatibility_normalise(text: str) -> str:
    """Diagnostic-only comparison for PDF text-layer Unicode artefacts."""
    decomposed = unicodedata.normalize("NFKD", _normalise(text))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _catalog(catalog: dict) -> dict[str, dict]:
    if catalog.get("schema") != "ayt-history-meb-source-catalog-v1":
        raise ValueError("MEB kaynak kataloğu gerekli")
    entries = {row.get("id"): row for row in catalog.get("sources", [])}
    if not entries or len(entries) != len(catalog.get("sources", [])):
        raise ValueError("MEB kaynak kataloğunda benzersiz kaynak kimlikleri gerekli")
    return entries


def build(candidate_pack: dict, source_catalog: dict, source_root: Path) -> dict:
    if candidate_pack.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("Özgün aday paketi gerekli")
    questions = candidate_pack.get("questions", [])
    if len(questions) != 120:
        raise ValueError("Tam 120 aday soru gerekli")
    sources = _catalog(source_catalog)
    root = source_root.resolve()
    documents: dict[str, pymupdf.Document] = {}
    records = []
    try:
        for question in questions:
            evidence = question.get("source_evidence", {})
            source = sources.get(evidence.get("source_id"))
            relative_path = Path(str(source.get("relative_path", ""))) if source else Path()
            path = (root / relative_path).resolve()
            if (source is None or source.get("source_checksum") != evidence.get("source_checksum")
                    or relative_path.is_absolute() or ".." in relative_path.parts
                    or not path.is_relative_to(root) or not path.is_file()):
                raise ValueError("Aday kanıtı checksum bağlı yerel kaynakla eşleşmiyor")
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            if checksum != source["source_checksum"]:
                raise ValueError("Yerel MEB PDF checksum'ı katalogla uyuşmuyor")
            document = documents.setdefault(source["id"], pymupdf.open(path))
            page_number = evidence.get("page")
            if not isinstance(page_number, int) or not 1 <= page_number <= len(document):
                raise ValueError("Kanıt sayfası kaynak sınırı dışında")
            page = document[page_number - 1]
            rect = pymupdf.Rect(evidence.get("bbox", []))
            if rect.is_empty or not page.rect.contains(rect):
                raise ValueError("Kanıt bbox değeri kaynak sayfası dışında")
            quote = _normalise(str(evidence.get("quote", "")))
            crop_text = _normalise(page.get_text("text", clip=rect))
            quote_present = bool(quote) and quote in crop_text
            padded = rect + (-18, -18, 18, 18)
            padded &= page.rect
            padded_crop_text = _normalise(page.get_text("text", clip=padded))
            padded_match = not quote_present and bool(quote) and quote in padded_crop_text
            unicode_compatible = (not quote_present and bool(quote)
                                  and _unicode_compatibility_normalise(quote) in _unicode_compatibility_normalise(crop_text))
            similarity = round(difflib.SequenceMatcher(None, quote, crop_text).ratio(), 4) if quote and crop_text else 0.0
            status = "pdf_crop_text_verified" if quote_present else (
                "review_required_bbox_expansion_candidate" if padded_match else (
                    "review_required_unicode_normalization" if unicode_compatible else (
                        "review_required_near_match" if similarity >= 0.9 else "review_required")))
            records.append({"id": question.get("id"), "source_id": source["id"], "source_checksum": checksum,
                            "page": page_number, "bbox": evidence["bbox"], "quote_sha256": hashlib.sha256(quote.encode()).hexdigest(),
                            "crop_text_sha256": hashlib.sha256(crop_text.encode()).hexdigest(),
                            "quote_present_in_bbox": quote_present,
                            "quote_present_in_padded_bbox": padded_match,
                            "unicode_compatibility_match": unicode_compatible,
                            "character_similarity": similarity, "status": status})
    finally:
        for document in documents.values():
            document.close()
    verified = sum(row["quote_present_in_bbox"] for row in records)
    return {"schema": SCHEMA, "candidate_checksum": candidate_pack["candidate_checksum"],
            "source_catalog_checksum": hashlib.sha256(json.dumps(source_catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "records": records, "summary": {"candidate_count": len(records), "verified_quote_count": verified,
            "review_required_count": len(records) - verified,
            "unicode_normalization_review_count": sum(row["unicode_compatibility_match"] for row in records),
            "bbox_expansion_review_count": sum(row["quote_present_in_padded_bbox"] for row in records),
            "near_match_review_count": sum(row["status"] == "review_required_near_match" for row in records)}, "runtime_enabled": False,
            "is_human_teacher_approval": False,
            "notice": "Deterministic local PDF crop-text audit only. A matching quote is not pedagogical approval or runtime release."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--source-catalog", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.candidate_pack), load(args.source_catalog), args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
