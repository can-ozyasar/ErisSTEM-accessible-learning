import pytest

from app.pipeline.accessible_content import CanonicalAccessibleBlock, release_decision


def payload(kind: str = "paragraph") -> dict:
    return {
        "id": "p1-b1",
        "kind": kind,
        "source_checksum": "a" * 64,
        "page": 1,
        "bbox": [1, 2, 30, 40],
        "reading_order": 1,
        "representations": {"navigation_label": "Paragraf", "spoken_text": "Doğrulanmış içerik."},
        "quality": {
            "source_bound": True,
            "schema_valid": True,
            "render_valid": True,
            "source_agreement": 1,
            "confidence": 1,
            "gold_gate_passed": True,
            "critical_error_count": 0,
        },
    }


def test_high_quality_text_can_bypass_teacher_exception_queue():
    decision, reasons = release_decision(CanonicalAccessibleBlock.model_validate(payload()))

    assert decision == "auto-approved"
    assert reasons == ["all-automatic-quality-gates-passed"]


def test_formula_requires_type_specific_gold_evidence_and_accessibility_outputs():
    item = payload("formula")
    item["representations"] = {"navigation_label": "Formül", "spoken_text": "a kare", "mathml": "<math></math>"}
    item["quality"]["gold_gate_passed"] = False

    decision, reasons = release_decision(CanonicalAccessibleBlock.model_validate(item))

    assert decision == "review-required"
    assert "type-specific-gold-gate-not-passed" in reasons


def test_critical_source_or_render_failure_is_blocked_not_sent_to_students():
    item = payload("table")
    item["quality"]["source_bound"] = False

    decision, reasons = release_decision(CanonicalAccessibleBlock.model_validate(item))

    assert decision == "blocked"
    assert reasons == ["source-not-bound"]


def test_formula_cannot_be_made_publishable_without_mathml_and_spoken_text():
    item = payload("formula")
    item["representations"] = {"navigation_label": "Formül"}

    with pytest.raises(ValueError, match="MathML"):
        CanonicalAccessibleBlock.model_validate(item)
