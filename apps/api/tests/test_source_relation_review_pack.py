import hashlib

import pymupdf

from app.pipeline.source_relation_review_pack import build


def test_review_pack_is_checksum_bound_and_does_not_approve_relation(tmp_path):
    pdf_path = tmp_path / "history.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Kaynak metni")
    document.save(pdf_path)
    document.close()
    checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    corpus = {"schema": "multi-history-rag-v1", "corpus_checksum": "corpus-v1", "books": [{
        "grade": 12, "source_name": "history.pdf", "source_checksum": checksum, "index": {"chunks": []},
    }]}
    proposals = {"schema": "deepseek-source-relation-proposals-v1", "corpus_checksum": "corpus-v1", "sources": [{
        "source_checksum": checksum, "chunk_id": "chunk-one", "page": 1, "bbox": [60, 50, 250, 100],
        "facts": [{"subject": "Kişi", "relation": "iliskilidir", "object": "Olay",
                   "review_status": "teacher_pdf_crop_required"}],
    }]}
    result = build(proposals, corpus, tmp_path, tmp_path / "pack")
    assert result["review_count"] == 1
    assert result["relation_count"] == 1
    assert (tmp_path / "pack" / "index.html").is_file()
    assert "No relation is approved" in result["notice"]
