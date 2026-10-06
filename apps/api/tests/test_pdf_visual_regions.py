from pathlib import Path

import pymupdf

from app.pipeline.pdf_visual_regions import render_visual_regions


def test_renders_only_routed_visual_region(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "image.pdf"
    image_path = tmp_path / "pixel.png"
    image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2, 2), False)
    image.clear_with(0xFF0000)
    image.save(image_path)
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_image(pymupdf.Rect(40, 40, 80, 80), filename=str(image_path))
    pdf.save(pdf_path)
    pdf.close()

    output_dir = tmp_path / "regions"
    result = render_visual_regions(pdf_path, source_root, output_dir, {1})

    assert len(result.assets) == 1
    assert (output_dir / result.assets[0].asset_path).is_file()
    assert len(result.assets[0].asset_checksum) == 64
