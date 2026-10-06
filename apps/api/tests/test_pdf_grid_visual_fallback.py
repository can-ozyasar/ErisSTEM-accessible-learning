from pathlib import Path

import pymupdf

from app.pipeline.pdf_grid_visual_fallback import render_grid_visual_fallback


def test_merges_adjacent_low_binding_grids_into_one_visual_asset(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "two-grids.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    for offset in (40, 142):
        for coordinate in (0, 40, 80):
            page.draw_line((offset, 80 + coordinate), (offset + 80, 80 + coordinate))
            page.draw_line((offset + coordinate, 80), (offset + coordinate, 160))
    pdf.save(pdf_path)
    pdf.close()

    result = render_grid_visual_fallback(pdf_path, source_root, tmp_path / "regions", {1})

    assert len(result.assets) == 1
    assert result.assets[0].pixel_size[0] > 300
    assert (tmp_path / "regions" / result.assets[0].asset_path).is_file()
