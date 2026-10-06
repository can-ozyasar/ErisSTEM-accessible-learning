from pathlib import Path

import pymupdf

from app.pipeline.pdf_vector_grid import extract_grid_geometry


def test_extracts_nonsemantic_cell_geometry_from_vector_grid(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "grid.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    for coordinate in (40, 80, 120):
        page.draw_line((40, coordinate), (120, coordinate))
        page.draw_line((coordinate, 40), (coordinate, 120))
    pdf.save(pdf_path)
    pdf.close()

    result = extract_grid_geometry(pdf_path, source_root, {1})

    assert len(result.cells) == 4
    assert {(cell.row, cell.column) for cell in result.cells} == {(1, 1), (1, 2), (2, 1), (2, 2)}
    assert all(cell.source.page == 1 for cell in result.cells)
    assert all(cell.publication_status == "requires-schema-validation-and-review" for cell in result.cells)
