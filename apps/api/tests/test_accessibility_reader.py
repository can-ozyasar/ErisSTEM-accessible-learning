import pytest

from app.pipeline.accessibility_reader import build_reading_plan
from app.pipeline.accessible_content import CanonicalAccessibleBlock


def block(block_id: str, order: int, *, braille: bool = False, confidence: float = 1.0):
    return CanonicalAccessibleBlock.model_validate(
        {
            "id": block_id,
            "kind": "paragraph",
            "source_checksum": "a" * 64,
            "page": 1,
            "bbox": [1, order, 30, order + 1],
            "reading_order": order,
            "representations": {
                "navigation_label": f"Paragraf {order}",
                "spoken_text": f"Doğrulanmış metin {order}.",
                **({"braille_source": f"Doğrulanmış metin {order}."} if braille else {}),
            },
            "quality": {
                "source_bound": True,
                "schema_valid": True,
                "render_valid": True,
                "source_agreement": 1,
                "confidence": confidence,
                "gold_gate_passed": True,
                "critical_error_count": 0,
            },
        }
    )


def test_reading_plan_is_ordered_and_exposes_braille_availability_not_fake_braille():
    plan = build_reading_plan([block("second", 2), block("first", 1, braille=True)])

    assert [unit.id for unit in plan.units] == ["first", "second"]
    assert plan.units[0].braille_available is True
    assert plan.units[1].braille_available is False


def test_reading_plan_refuses_a_low_confidence_candidate():
    with pytest.raises(ValueError, match="not safe"):
        build_reading_plan([block("uncertain", 1, confidence=0.7)])
