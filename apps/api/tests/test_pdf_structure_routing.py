from pathlib import Path

import pymupdf

from app.pipeline.pdf_structure_routing import build_structure_routing_plan


def test_routes_vector_geometry_and_non_overlapping_embedded_image(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "hybrid.pdf"
    image_path = tmp_path / "pixel.png"
    image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2, 2), False)
    image.clear_with(0xFF0000)
    image.save(image_path)
    pdf = pymupdf.open()
    page = pdf.new_page()
    for coordinate in (40, 80, 120):
        page.draw_line((40, coordinate), (120, coordinate))
        page.draw_line((coordinate, 40), (coordinate, 120))
    page.insert_image(pymupdf.Rect(180, 40, 220, 80), filename=str(image_path))
    pdf.save(pdf_path)
    pdf.close()

    plan = build_structure_routing_plan(pdf_path, source_root, {1})

    routes = {route.route for route in plan.routes}
    assert "vector-geometry-benchmark" in routes
    assert "visual-model-benchmark" in routes
    assert all(route.review_required for route in plan.routes)
    assert all(route.source.page == 1 for route in plan.routes)
