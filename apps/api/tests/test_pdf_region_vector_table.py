import hashlib
import json
from pathlib import Path

import pymupdf

from app.pipeline.pdf_region_vector_table import extract_region_vector_tables


def test_extracts_private_region_table_from_vector_lines_and_native_words(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "table.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    for coordinate in (40, 120, 200):
        page.draw_line((40, coordinate), (200, coordinate))
        page.draw_line((coordinate, 40), (coordinate, 200))
    page.insert_text((60, 80), "Baslik")
    page.insert_text((140, 160), "Deger")
    pdf.save(pdf_path)
    pdf.close()
    checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    manifest = tmp_path / "regions.json"
    manifest.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "route_id": "table-1",
                        "source": {"page": 1, "bbox": [40, 40, 200, 200], "source_checksum": checksum},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = extract_region_vector_tables(pdf_path, source_root, manifest)

    assert result[0].status == "candidate-vector-native-needs-gold-and-review"
    assert (result[0].grid_rows, result[0].grid_columns, result[0].bound_word_count) == (2, 2, 2)
    assert {(cell["row"], cell["column"], cell["text"]) for cell in result[0].draft["cells"]} >= {
        (1, 1, "Baslik"),
        (2, 2, "Deger"),
    }
