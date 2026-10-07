import hashlib
import json
from pathlib import Path

import pymupdf

from app.job_store import DocumentStore, TableReviewStore, make_session_factory
from app.pipeline.import_vector_native_table_reviews import import_vector_native_table_reviews


def test_import_creates_source_bound_teacher_table_and_is_idempotent(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "table.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    for coordinate in (40, 120, 200):
        page.draw_line((40, coordinate), (200, coordinate))
        page.draw_line((coordinate, 40), (coordinate, 200))
    page.insert_text((60, 80), "Baslik")
    pdf.save(pdf_path)
    pdf.close()
    checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    regions = tmp_path / "regions.json"
    regions.write_text(json.dumps({"assets": [{"route_id": "grid-1", "source": {"page": 1, "bbox": [40, 40, 200, 200], "source_checksum": checksum}}]}), encoding="utf-8")
    sessions = make_session_factory(f"sqlite:///{tmp_path / 'reviews.db'}")
    documents, tables = DocumentStore(sessions), TableReviewStore(sessions)

    first = import_vector_native_table_reviews(pdf_path, source_root, regions, tmp_path / "derived", documents, tables)
    second = import_vector_native_table_reviews(pdf_path, source_root, regions, tmp_path / "derived", documents, tables)

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["existing"] == 1
    assert (tmp_path / "derived" / "review-pages" / first["document_id"] / "page-1.png").is_file()
