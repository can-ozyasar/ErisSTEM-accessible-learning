from pathlib import Path

import pymupdf

from app.pipeline.pdf_vector_evidence import extract_vector_evidence


def test_extracts_vector_and_image_evidence_with_coordinates(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "geometry.pdf"
    image_path = tmp_path / "pixel.png"
    image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2, 2), False)
    image.clear_with(0xFF0000)
    image.save(image_path)
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.draw_rect(pymupdf.Rect(20, 30, 120, 80))
    page.insert_image(pymupdf.Rect(150, 30, 170, 50), filename=str(image_path))
    pdf.save(pdf_path)
    pdf.close()

    result = extract_vector_evidence(pdf_path, source_root, {1})

    page_evidence = result.pages[0]
    assert page_evidence.route == "vector-geometry-available"
    assert page_evidence.drawing_count >= 1
    assert page_evidence.embedded_image_count == 1
    assert {region.kind for region in page_evidence.regions} == {"vector-drawing", "embedded-image"}
    assert all(region.source.page == 1 for region in page_evidence.regions)
    assert all(region.source.bbox[0] < region.source.bbox[2] for region in page_evidence.regions)
