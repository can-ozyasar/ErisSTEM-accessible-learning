import json
from pathlib import Path

import pymupdf

from app.pipeline.prepare_formula_regions import prepare_formula_regions


def test_formula_regions_are_cropped_from_teacher_coordinates_and_keep_gold_separate(tmp_path: Path):
    root = tmp_path / "meb"
    root.mkdir()
    source = root / "math.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "5 / 3")
    document.save(source)
    document.close()
    annotations = tmp_path / "annotations.json"
    annotations.write_text(json.dumps({"schema_version": "formula-region-annotations-v1", "formulas": [{
        "id": "fraction-01", "page": 1, "bbox": [60, 50, 120, 90], "visible_notation": "5/3", "spoken_text": "beş bölü üç"
    }]}), encoding="utf-8")
    inputs, gold = prepare_formula_regions(source, root, annotations, tmp_path / "benchmark", tmp_path / "private-gold.json")
    assert inputs["regions"][0]["id"] == gold["formulas"][0]["id"]
    assert "visible_notation" not in inputs["regions"][0]
    assert (tmp_path / "benchmark" / "images" / "fraction-01.png").is_file()
