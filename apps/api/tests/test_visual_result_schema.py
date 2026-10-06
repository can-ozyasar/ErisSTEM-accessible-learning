import pytest
from pydantic import ValidationError

from app.pipeline.visual_result_schema import VisualTableDraft


def table_payload() -> dict:
    return {
        "kind": "table",
        "source": {
            "region_id": "p51-image-1-visual",
            "source_checksum": "a" * 64,
            "page": 51,
            "bbox": [1, 2, 30, 40],
        },
        "cells": [{"row": 1, "column": 1, "role": "header", "text": "Başlık", "confidence": 0.9}],
        "confidence": 0.9,
    }


def test_visual_table_schema_rejects_unknown_fields_and_duplicate_cells():
    assert VisualTableDraft.model_validate(table_payload()).cells[0].text == "Başlık"
    duplicate = table_payload()
    duplicate["cells"].append(duplicate["cells"][0])
    with pytest.raises(ValidationError, match="unique"):
        VisualTableDraft.model_validate(duplicate)
    unknown = table_payload()
    unknown["html"] = "<table>"
    with pytest.raises(ValidationError):
        VisualTableDraft.model_validate(unknown)
