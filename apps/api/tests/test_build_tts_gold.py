import pytest

from app.pipeline.build_tts_gold import (
    CanonicalContentManifest,
    CriticalTokenManifest,
    build_tts_gold,
)


def block(block_id: str, *, confidence: float = 1.0) -> dict:
    return {
        "id": block_id, "kind": "formula", "source_checksum": "a" * 64, "page": 1,
        "bbox": [1, 2, 30, 40], "reading_order": 1,
        "representations": {"navigation_label": "Formül", "spoken_text": "x karesi eşittir dört", "mathml": "<math></math>"},
        "quality": {"source_bound": True, "schema_valid": True, "render_valid": True, "source_agreement": 1, "confidence": confidence, "gold_gate_passed": True, "critical_error_count": 0},
    }


def test_tts_gold_uses_only_auto_approved_spoken_content_and_preserves_review_labels():
    content = CanonicalContentManifest.model_validate({
        "schema_version": "canonical-accessible-content-v1", "blocks": [block("safe"), block("uncertain", confidence=0.7)],
    })
    critical = CriticalTokenManifest.model_validate({
        "schema_version": "tts-critical-tokens-v1", "tokens_by_block_id": {"safe": ["karesi", "eşittir"]},
    })

    result = build_tts_gold(content, critical)

    assert [item.id for item in result.items] == ["safe"]
    assert result.items[0].critical_tokens == ["karesi", "eşittir"]


def test_tts_gold_refuses_to_make_a_dataset_from_only_uncertain_content():
    content = CanonicalContentManifest.model_validate({
        "schema_version": "canonical-accessible-content-v1", "blocks": [block("uncertain", confidence=0.7)],
    })
    critical = CriticalTokenManifest.model_validate({"schema_version": "tts-critical-tokens-v1"})

    with pytest.raises(ValueError, match="no auto-approved"):
        build_tts_gold(content, critical)
