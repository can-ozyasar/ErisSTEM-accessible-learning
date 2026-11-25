import hashlib

import pymupdf

from app.pipeline.audit_ayt_history_candidate_crops import (
    _normalise,
    _unicode_compatibility_normalise,
    build,
)


def test_normalisation_joins_pdf_soft_hyphen_line_wraps_only():
    assert _normalise("dep\u00ad\nremi") == "depremi"
    assert _normalise("savaş-\nları") == "savaşları"
    assert _unicode_compatibility_normalise("BİLGİ") == _unicode_compatibility_normalise("bilgi")


def test_checks_quote_against_its_exact_pdf_bbox(tmp_path):
    pdf = tmp_path / "source.pdf"
    with pymupdf.open() as document:
        page = document.new_page(width=300, height=300)
        page.insert_text((30, 80), "Kaynakta dogrulanan tarih bilgisi yer alir.")
        document.save(pdf)
    checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
    questions = [{"id": f"q-{number:03d}", "source_evidence": {
        "source_id": "meb-source-01", "source_checksum": checksum, "page": 1,
        "bbox": [20, 50, 290, 100], "quote": "Kaynakta dogrulanan tarih bilgisi yer alir."}}
                 for number in range(120)]
    pack = {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64,
            "questions": questions}
    catalog = {"schema": "ayt-history-meb-source-catalog-v1", "sources": [{"id": "meb-source-01",
               "source_checksum": checksum, "relative_path": pdf.name}]}
    result = build(pack, catalog, tmp_path)
    assert result["summary"] == {"candidate_count": 120, "verified_quote_count": 120, "review_required_count": 0,
                                 "unicode_normalization_review_count": 0, "bbox_expansion_review_count": 0,
                                 "near_match_review_count": 0}
    assert result["runtime_enabled"] is False


def test_marks_nonmatching_quote_for_review(tmp_path):
    pdf = tmp_path / "source.pdf"
    with pymupdf.open() as document:
        document.new_page(width=300, height=300)
        document.save(pdf)
    checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
    questions = [{"id": f"q-{number:03d}", "source_evidence": {
        "source_id": "meb-source-01", "source_checksum": checksum, "page": 1,
        "bbox": [20, 50, 290, 100], "quote": "Bu metin PDFde yoktur."}}
                 for number in range(120)]
    pack = {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "a" * 64,
            "questions": questions}
    catalog = {"schema": "ayt-history-meb-source-catalog-v1", "sources": [{"id": "meb-source-01",
               "source_checksum": checksum, "relative_path": pdf.name}]}
    result = build(pack, catalog, tmp_path)
    assert result["summary"]["review_required_count"] == 120
