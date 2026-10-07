import hashlib
import json
from pathlib import Path

import pymupdf

from app.pipeline.symbol_cell_benchmark import prepare_symbol_cell_benchmark


def test_symbol_cell_package_separates_images_from_expected_gold(tmp_path: Path):
    source_root = tmp_path / "meb"
    source_root.mkdir()
    pdf_path = source_root / "table.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    for coordinate in (40, 120, 200):
        page.draw_line((40, coordinate), (200, coordinate))
        page.draw_line((coordinate, 40), (coordinate, 200))
    page.insert_text((60, 80), "∈")
    pdf.save(pdf_path)
    pdf.close()
    checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps({"schema_version": "visual-table-gold-v1", "tables": [{"schema_version": "visual-table-gold-v1", "kind": "table", "source": {"region_id": "grid", "source_checksum": checksum, "page": 1, "bbox": [40, 40, 200, 200]}, "cells": [{"row": 1, "column": 1, "role": "header", "text": "∈"}]}]}), encoding="utf-8")

    package = tmp_path / "package"
    expected_path = tmp_path / "private-gold.json"
    inputs, expected = prepare_symbol_cell_benchmark(
        pdf_path, source_root, gold_path, package, expected_path
    )

    assert len(inputs["assets"]) == len(expected["expected"]) == 1
    assert "expected" not in inputs["assets"][0]
    assert (package / inputs["assets"][0]["asset_path"]).is_file()
    assert not (package / "symbol-cell-gold-v1.json").exists()
    assert json.loads(expected_path.read_text(encoding="utf-8")) == expected
