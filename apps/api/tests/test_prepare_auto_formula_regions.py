from pathlib import Path

import pymupdf

from app.pipeline.prepare_auto_formula_regions import prepare


def test_same_baseline_fragments_become_one_whole_formula_crop(tmp_path: Path):
    root = tmp_path / "meb"
    root.mkdir()
    source = root / "math.pdf"
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "2^(3/2) = root(8)")
    pdf.save(source)
    pdf.close()
    document = {"id": "source-test", "blocks": [
        {"id": "left", "kind": "formula-display", "reading_order": 1, "status": "review_required", "source": {"page": 1, "bbox": [60, 60, 100, 80]}},
        {"id": "right", "kind": "formula-display", "reading_order": 2, "status": "review_required", "source": {"page": 1, "bbox": [110, 61, 180, 81]}},
        {"id": "next-row", "kind": "formula-display", "reading_order": 3, "status": "review_required", "source": {"page": 1, "bbox": [60, 95, 100, 115]}},
    ]}

    manifest, bindings = prepare(document, source, root, tmp_path / "regions")

    assert len(manifest["regions"]) == 2
    assert bindings["bindings"][0]["block_ids"] == ["left", "right"]
    assert (tmp_path / "regions" / manifest["regions"][0]["asset_path"]).is_file()
