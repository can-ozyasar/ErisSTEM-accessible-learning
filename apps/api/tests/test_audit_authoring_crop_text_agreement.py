import hashlib

import pymupdf

from app.pipeline.audit_authoring_crop_text_agreement import build


def test_audits_quote_against_checksum_bound_pdf(tmp_path):
    root = tmp_path / "meb"
    root.mkdir()
    pdf = root / "book.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Verified history source text")
    document.save(pdf)
    document.close()
    document = pymupdf.open(pdf)
    bbox = list(document[0].search_for("Verified history source text")[0])
    document.close()
    checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
    pack = {"schema": "ayt-history-authoring-source-crop-pack-v1", "corpus_checksum": "c", "queue_checksum": "q" * 64, "reviews": [{
        "id": "authoring-001", "source_checksum": checksum, "page": 1, "bbox": bbox,
        "quote": "Verified history source text"}]}
    result = build(pack, root)
    assert result["summary"] == {"reviewed": 1, "agreement_count": 1, "held_out": 0}
    assert result["records"][0]["pdf_crop_checked"] is False
