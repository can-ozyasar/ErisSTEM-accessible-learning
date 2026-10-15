from app.pipeline.import_formula_ocr import apply_formula_predictions


def test_imported_whole_formula_is_normal_notation_and_keeps_teacher_review():
    document = {"id": "source-test", "blocks": [{
        "id": "b1", "kind": "formula-display", "revision": 1, "status": "review_required",
        "source": {"page": 1, "bbox": [1, 2, 3, 4], "extraction_step": "math-ocr-pending"},
    }, {
        "id": "b2", "kind": "formula-display", "revision": 1, "status": "review_required",
        "source": {"page": 1, "bbox": [4, 5, 6, 7], "extraction_step": "math-ocr-pending"},
    }]}
    manifest = {"schema_version": "formula-region-benchmark-input-v1", "regions": [{"id": "r1", "page": 1, "bbox": [10, 20, 30, 40]}]}
    predictions = {"schema_version": "formula-region-predictions-v1", "candidate": "test-model", "predictions": [{
        "id": "r1", "visible_notation": r"2^{\frac{3}{2}}=\sqrt{8}", "confidence": 0.0, "status": "completed",
    }]}
    bindings = {"schema_version": "formula-ocr-bindings-v1", "document_id": "source-test", "bindings": [{"region_id": "r1", "block_ids": ["b1", "b2"]}]}

    result, applied = apply_formula_predictions(document, manifest, predictions, bindings)

    assert applied == 1
    assert [block["id"] for block in result["blocks"]] == ["b1"]
    block = result["blocks"][0]
    assert block["text"] == "2^(3/2)=√(8)"
    assert block["latex"] == r"2^{\frac{3}{2}}=\sqrt{8}"
    assert "karekök içinde sekiz" in block["spoken_text"]
    assert block["status"] == "review_required"
    assert block["source"]["extraction_step"] == "formula-ocr:test-model"
