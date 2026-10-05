from app.pipeline.materialize import draft_from_text_layer
from app.pipeline.pdf_text_layer import ExtractedBlock, ExtractedDocument, SourceCoordinate


def test_materialized_text_is_never_published():
    checksum = "a" * 64
    result = ExtractedDocument(
        checksum,
        1,
        [
            ExtractedBlock(
                "p1-b1", "paragraph", 1, "Metin", SourceCoordinate(1, (1, 1, 2, 2), checksum)
            )
        ],
    )
    draft = draft_from_text_layer(result, "Taslak")
    assert draft["published_revision"] == 0
    assert draft["blocks"][0]["status"] == "review_required"
