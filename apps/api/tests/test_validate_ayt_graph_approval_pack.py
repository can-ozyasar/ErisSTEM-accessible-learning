import hashlib
from pathlib import Path

import pymupdf
import pytest

from app.pipeline.build_ayt_graph_approval_pack import build
from app.pipeline.validate_ayt_graph_approval_pack import validate


def test_pack_validator_checks_crop_integrity(tmp_path: Path):
    pdf_path = tmp_path / "book.pdf"
    document = pymupdf.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "1920 yılında TBMM açıldı.")
    document.save(pdf_path)
    checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "0" * 32, "books": [{
        "source_name": "book.pdf", "source_checksum": checksum,
        "index": {"chunks": [{"id": "c1", "section_id": "1.1", "section_title": "Millî Mücadele",
                                 "page": 1, "bbox": [20, 20, 380, 140], "text": "kanıt"}]},
    }]}
    output = tmp_path / "pack"
    manifest = build(corpus, tmp_path, output)
    result = validate(manifest, output)
    assert result["security_passed"] and result["review_count"] == 1
    (output / manifest["reviews"][0]["crop"]).unlink()
    with pytest.raises(ValueError, match="crop"):
        validate(manifest, output)
