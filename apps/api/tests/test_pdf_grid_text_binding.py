from pathlib import Path

import pymupdf

from app.pipeline.pdf_grid_text_binding import bind_grid_text


def test_binds_only_unambiguous_native_text_to_grid_cells(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "grid.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    for coordinate in (40, 120, 200):
        page.draw_line((40, coordinate), (200, coordinate))
        page.draw_line((coordinate, 40), (coordinate, 200))
    page.insert_text((60, 80), "Sol ust")
    page.insert_text((140, 160), "Sag alt")
    pdf.save(pdf_path)
    pdf.close()

    result = bind_grid_text(pdf_path, source_root, {1})

    bound = [cell for cell in result.cells if cell.binding_status == "bound-native-text"]
    assert len(bound) == 2
    assert {cell.text for cell in bound} == {"Sol ust", "Sag alt"}
    assert all(cell.publication_status == "requires-schema-validation-and-review" for cell in result.cells)
    assert result.summaries[0].route == "candidate-table-schema-validation"
