import hashlib

from fastapi.testclient import TestClient

from app.main import app, demo_document, document_store
from app.pipeline.accessibility_reader import ReadingUnit
from app.pipeline.braille_adapter import BrailleUnavailable, translate_verified_literary


def unit(text: str, *, kind: str = "paragraph") -> ReadingUnit:
    return ReadingUnit(
        id="unit-1", kind=kind, navigation_label="Paragraf", spoken_text=text,
        braille_available=True, reading_order=1,
    )


def test_actual_turkish_liblouis_translation_is_source_bound():
    result = translate_verified_literary(unit("Merhaba, Türkiye!"))

    assert result.code == "turkish-literary-grade-1"
    assert result.cells.startswith("⠠⠍")
    assert all("\u2800" <= char <= "\u28ff" for char in result.cells)
    assert result.source_sha256 == hashlib.sha256("Merhaba, Türkiye!".encode()).hexdigest()


def test_literary_braille_rejects_math_symbols():
    try:
        translate_verified_literary(unit("A ∈ B"))
    except BrailleUnavailable:
        pass
    else:
        raise AssertionError("A literary table must not encode mathematical notation")


def test_formula_cannot_use_literary_braille_table():
    try:
        translate_verified_literary(unit("x karesi", kind="formula"))
    except BrailleUnavailable:
        pass
    else:
        raise AssertionError("Mathematics must not be passed through literary Braille")


def test_student_braille_endpoint_requires_verified_published_unit():
    document_store.reset_for_test(demo_document.model_dump(mode="json"))
    client = TestClient(app)
    denied = client.get("/v1/student/documents/synthetic-geometry-01/braille/formula-1", headers={"X-Role": "student"})
    available = client.get("/v1/student/documents/synthetic-geometry-01/braille/heading-1", headers={"X-Role": "student"})

    assert denied.status_code == 404
    assert available.status_code == 200
    assert available.json()["unit_id"] == "heading-1"
