from pathlib import Path

from app.pipeline.pdf_text_layer import ExtractedBlock, ExtractedDocument, SourceCoordinate
from app.pipeline.worker import write_text_layer


def test_different_page_scopes_do_not_overwrite_each_other(tmp_path: Path):
    checksum = "a" * 64
    first = ExtractedDocument(
        checksum,
        10,
        [ExtractedBlock("p1", "paragraph", 1, "A", SourceCoordinate(1, (1, 1, 2, 2), checksum))],
    )
    second = ExtractedDocument(
        checksum,
        10,
        [ExtractedBlock("p2", "paragraph", 1, "B", SourceCoordinate(2, (1, 1, 2, 2), checksum))],
    )
    assert write_text_layer(first, tmp_path) != write_text_layer(second, tmp_path)
