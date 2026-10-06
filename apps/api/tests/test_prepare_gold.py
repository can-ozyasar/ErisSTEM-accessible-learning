from app.pipeline.prepare_gold import parse_item


def test_parse_gold_item():
    assert parse_item("formula:22") == {
        "id": "formula-p22",
        "page": 22,
        "kind": "formula",
        "expected": "",
    }
