from app.pipeline.materialize import draft_from_text_layer, looks_like_fragmented_math
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


def test_fragmented_math_is_not_sent_to_the_prose_editor():
    assert looks_like_fragmented_math("2 2 3 2 2 8 2 3 3 2 = =")
    assert not looks_like_fragmented_math("Üslü Gösterim Köklü Gösterime Dönüştürme")
