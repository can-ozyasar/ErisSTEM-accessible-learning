import hashlib
from pathlib import Path

import pymupdf

from app.pipeline.build_ayt_graph_approval_pack import build


def test_build_graph_approval_pack_renders_private_crop(tmp_path: Path):
    pdf_path = tmp_path / "book.pdf"
    document = pymupdf.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((40, 80), "1920 yılında TBMM açıldı.")
    document.save(pdf_path)
    checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "0" * 32, "books": [{
        "source_name": "book.pdf", "source_checksum": checksum,
        "index": {"chunks": [{"id": "c1", "section_id": "1.1", "section_title": "Millî Mücadele",
                                 "page": 1, "bbox": [20, 20, 380, 140],
                                 "text": "1920 yılında TBMM açıldı."}]},
    }]}
    output = tmp_path / "pack"
    manifest = build(corpus, tmp_path, output)
    assert manifest["review_count"] == 1
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "Onay manifestini indir" in html
    assert "approved_for_runtime" in html
    assert (output / "index.html").is_file()
    assert next((output / "crops").glob("*.png")).is_file()
