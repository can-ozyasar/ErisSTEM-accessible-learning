import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app, demo_document, document_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_document_store():
    document_store.reset_for_test(demo_document.model_dump(mode="json"))


def test_student_never_receives_unreviewed_formula():
    response = client.get(
        "/v1/student/documents/synthetic-geometry-01", headers={"X-Role": "student"}
    )
    assert response.status_code == 200
    assert [block["id"] for block in response.json()["blocks"]] == ["heading-1", "paragraph-1"]


def test_missing_development_identity_is_rejected():
    response = client.get("/v1/student/documents/synthetic-geometry-01")
    assert response.status_code == 401


def test_development_role_header_is_disabled_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    response = client.get("/health", headers={"X-Role": "student"})
    assert response.status_code == 503
    monkeypatch.delenv("APP_ENV", raising=False)


def test_teacher_correction_then_reviewer_publish():
    draft = client.get(
        "/v1/teacher/documents/synthetic-geometry-01", headers={"X-Role": "teacher"}
    ).json()
    formula = next(item for item in draft["blocks"] if item["id"] == "formula-1")
    correction = client.put(
        "/v1/teacher/documents/synthetic-geometry-01/blocks/formula-1",
        headers={"X-Role": "teacher"},
        json={
            "latex": "a^2 + b^2 = c^2",
            "mathml": "<math><mi>a</mi><mo>+</mo><mi>b</mi><mo>=</mo><mi>c</mi></math>",
            "reason": "Kaynak görselde hipotenüsün karesi var.",
            "expected_revision": formula["revision"],
        },
    )
    assert correction.status_code == 200
    publish = client.post(
        "/v1/reviewer/documents/synthetic-geometry-01/publish", headers={"X-Role": "reviewer"}
    )
    assert publish.status_code == 200
    student = client.get(
        "/v1/student/documents/synthetic-geometry-01", headers={"X-Role": "student"}
    ).json()
    assert any(block["latex"] == "a^2 + b^2 = c^2" for block in student["blocks"])


def test_only_admin_can_queue_and_duplicate_job_is_reused():
    payload = {
        "source_checksum": hashlib.sha256(uuid4().bytes).hexdigest(),
        "source_relative_path": "matematik/kitap.pdf",
        "pipeline_version": "text-layer-v1",
    }
    denied = client.post("/v1/admin/processing-jobs", headers={"X-Role": "teacher"}, json=payload)
    first = client.post("/v1/admin/processing-jobs", headers={"X-Role": "admin"}, json=payload)
    second = client.post("/v1/admin/processing-jobs", headers={"X-Role": "admin"}, json=payload)

    assert denied.status_code == 403
    assert first.status_code == 201
    assert first.json()["created"] is True
    assert second.status_code == 201
    assert second.json()["created"] is False
    assert second.json()["id"] == first.json()["id"]
