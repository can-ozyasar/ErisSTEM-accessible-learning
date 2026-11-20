import hashlib

import pymupdf

from app.pipeline.render_authoring_source_crop_pack import build


def test_renders_checksum_bound_crop(tmp_path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf = source_root / "tarih.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Kaynak kanıt metni")
    document.save(pdf)
    document.close()
    checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
    gate = {"schema": "ayt-history-authoring-source-gate-v1", "corpus_checksum": "c", "queue_checksum": "q" * 64,
            "accepted_for_pdf_crop_review": [{"card": {"id": "authoring-001", "source_evidence": {
                "source_checksum": checksum, "grade": 12, "section_id": "1.1", "section_title": "Konu",
                "source_id": "tarih.pdf", "page": 1, "bbox": [60, 60, 220, 110], "atom_id": "atom", "quote": "Kaynak kanıt metni"}},
                "ai_review": {"verdict": "direct_fact"}}]}
    result = build(gate, source_root, tmp_path / "pack")
    assert result["review_count"] == 1
    assert (tmp_path / "pack" / result["reviews"][0]["crop"]).is_file()
    assert result["reviews"][0]["pdf_crop_checked"] is False
