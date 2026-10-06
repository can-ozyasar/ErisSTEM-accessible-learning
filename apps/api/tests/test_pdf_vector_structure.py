from pathlib import Path

import pymupdf

from app.pipeline.pdf_vector_structure import extract_vector_structure


def test_extracts_grid_and_axis_candidates_with_source_coordinates(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "geometry.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    for coordinate in (40, 80, 120):
        page.draw_line((40, coordinate), (120, coordinate))
        page.draw_line((coordinate, 40), (coordinate, 120))
    page.draw_line((180, 180), (260, 180))
    page.draw_line((180, 180), (180, 100))
    pdf.save(pdf_path)
    pdf.close()

    result = extract_vector_structure(pdf_path, source_root, {1})

    kinds = {candidate.kind for candidate in result.candidates}
    assert "rectilinear-grid-candidate" in kinds
    assert "perpendicular-axis-candidate" in kinds
    assert all(candidate.source.page == 1 for candidate in result.candidates)
    assert all(candidate.publication_status == "requires-benchmark-and-review" for candidate in result.candidates)
