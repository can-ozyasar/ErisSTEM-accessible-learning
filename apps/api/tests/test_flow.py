import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import SAMPLE_CHECKSUM, app, demo_document, document_store, table_review_store
from app.pipeline.materialize import draft_from_text_layer
from app.pipeline.pdf_text_layer import ExtractedBlock, ExtractedDocument, SourceCoordinate

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_document_store():
    document_store.reset_for_test(demo_document.model_dump(mode="json"))
    table_review_store.reset_for_test()


def test_student_never_receives_unreviewed_formula():
    response = client.get(
        "/v1/student/documents/synthetic-geometry-01", headers={"X-Role": "student"}
    )
    assert response.status_code == 200
    assert [block["id"] for block in response.json()["blocks"]] == ["heading-1", "paragraph-1"]


def test_student_document_catalog_excludes_unpublished_drafts():
    hidden = demo_document.model_copy(deep=True)
    hidden.id = "unpublished-test-document"
    document_store.create_draft(hidden.model_dump(mode="json"))

    response = client.get("/v1/student/documents", headers={"X-Role": "student"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == ["synthetic-geometry-01"]
    assert "blocks" not in response.json()[0]
    assert client.get("/v1/student/documents/unpublished-test-document/tables", headers={"X-Role": "student"}).status_code == 404
    assert client.get("/v1/student/documents/missing/tables", headers={"X-Role": "student"}).status_code == 404


def test_student_reading_plan_exposes_only_verified_direct_text_units():
    response = client.get(
        "/v1/student/documents/synthetic-geometry-01/reading-plan", headers={"X-Role": "student"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert [unit["id"] for unit in payload["plan"]["units"]] == ["heading-1", "paragraph-1"]
    assert payload["unavailable_block_ids"] == []


def test_missing_development_identity_is_rejected():
    response = client.get("/v1/student/documents/synthetic-geometry-01")
    assert response.status_code == 401


def test_development_role_header_is_disabled_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    response = client.get("/health", headers={"X-Role": "student"})
    assert response.status_code == 503
    monkeypatch.delenv("APP_ENV", raising=False)


def test_teacher_can_approve_materialized_text_but_not_formula():
    checksum = "c" * 64
    extracted = ExtractedDocument(
        checksum,
        1,
        [
            ExtractedBlock(
                "p1-b1",
                "paragraph",
                1,
                "Doğrulanacak metin",
                SourceCoordinate(1, (1, 1, 2, 2), checksum),
            )
        ],
    )
    draft = draft_from_text_layer(extracted, "Taslak")
    document_store.create_draft(draft)
    response = client.post(
        f"/v1/teacher/documents/{draft['id']}/blocks/p1-b1/approve",
        headers={"X-Role": "teacher"},
        json={"reason": "Kaynak kutusuyla karşılaştırıldı.", "expected_revision": 1},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


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
            "mathml": "<math><msup><mi>a</mi><mn>2</mn></msup><mo>+</mo><msup><mi>b</mi><mn>2</mn></msup><mo>=</mo><msup><mi>c</mi><mn>2</mn></msup></math>",
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
    reading = client.get(
        "/v1/student/documents/synthetic-geometry-01/reading-plan", headers={"X-Role": "student"}
    ).json()
    assert reading["unavailable_block_ids"] == []
    assert reading["plan"]["units"][-1]["kind"] == "formula"
    assert reading["plan"]["units"][-1]["spoken_text"] == "a karesi artı b karesi eşittir c karesi"
    assert reading["plan"]["units"][-1]["braille_available"] is False


def test_unsupported_published_mathml_is_not_spoken_as_a_guess():
    draft = demo_document.model_copy(deep=True)
    formula = next(block for block in draft.blocks if block.kind == "formula-display")
    formula.mathml = "<math><mstyle><mi>x</mi></mstyle></math>"
    formula.validation.reasons = ["Öğretmen düzeltmesi"]
    formula.validation.render_score = formula.validation.source_agreement = formula.validation.confidence = 1
    formula.status = "published"
    document_store.publish(draft.model_dump(mode="json"))
    reading = client.get(
        "/v1/student/documents/synthetic-geometry-01/reading-plan", headers={"X-Role": "student"}
    ).json()
    assert "formula-1" in reading["unavailable_block_ids"]
    assert all(unit["id"] != "formula-1" for unit in reading["plan"]["units"])


def test_teacher_can_approve_supported_formula_speech_without_editing_latex():
    path = "/v1/teacher/documents/synthetic-geometry-01/blocks/formula-1"
    proposal = client.get(f"{path}/speech-proposal", headers={"X-Role": "teacher"})
    assert proposal.status_code == 200
    assert proposal.json()["proposed_spoken_text"] == "a karesi artı b karesi eşittir c"
    assert client.get(f"{path}/speech-proposal", headers={"X-Role": "student"}).status_code == 403
    approval = client.post(f"{path}/approve-formula", headers={"X-Role": "teacher"}, json={
        "reason": "Kaynak PDF ile Türkçe okunuş karşılaştırıldı.", "expected_revision": proposal.json()["expected_revision"],
    })
    assert approval.status_code == 200
    assert approval.json()["status"] == "approved"
    assert client.post(f"{path}/approve-formula", headers={"X-Role": "teacher"}, json={
        "reason": "Kaynak PDF ile Türkçe okunuş karşılaştırıldı.", "expected_revision": proposal.json()["expected_revision"],
    }).status_code == 409
    assert client.post("/v1/reviewer/documents/synthetic-geometry-01/publish", headers={"X-Role": "reviewer"}).status_code == 200
    reading = client.get("/v1/student/documents/synthetic-geometry-01/reading-plan", headers={"X-Role": "student"}).json()
    assert reading["plan"]["units"][-1]["spoken_text"] == proposal.json()["proposed_spoken_text"]


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


def test_vector_native_table_is_reviewed_at_source_then_published_separately():
    submission = {
        "id": "table-review-demo-1",
        "document_id": "synthetic-geometry-01",
        "schema_version": "visual-table-draft-v1",
        "kind": "table",
        "source": {
            "region_id": "synthetic-grid-1", "source_checksum": SAMPLE_CHECKSUM,
            "page": 1, "bbox": [72, 72, 300, 180],
        },
        "cells": [
            {"row": 1, "column": 1, "role": "header", "text": "Kenar", "confidence": 0.0},
            {"row": 1, "column": 2, "role": "header", "text": "Uzunluk", "confidence": 0.0},
            {"row": 2, "column": 1, "role": "data", "text": "a", "confidence": 0.0},
            {"row": 2, "column": 2, "role": "data", "text": "3", "confidence": 0.0},
        ],
        "confidence": 0.0,
        "publication_status": "requires-gold-and-teacher-review",
        "candidate_status": "candidate-vector-native-needs-gold-and-review",
    }
    created = client.post("/v1/admin/table-reviews", headers={"X-Role": "admin"}, json=submission)
    assert created.status_code == 201
    assert "confidence" not in created.json()
    assert "source_checksum" not in created.json()["source"]
    assert client.get("/v1/student/tables/table-review-demo-1", headers={"X-Role": "student"}).status_code == 404
    assert client.get("/v1/student/documents/synthetic-geometry-01/tables", headers={"X-Role": "student"}).json() == []

    queue = client.get("/v1/teacher/table-reviews", headers={"X-Role": "teacher"})
    assert [item["id"] for item in queue.json()] == ["table-review-demo-1"]
    approved = client.post(
        "/v1/teacher/table-reviews/table-review-demo-1/approve",
        headers={"X-Role": "teacher"},
        json={"reason": "Kaynak PDF koordinatındaki tabloyla karşılaştırıldı.", "expected_revision": 1},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    published = client.post(
        "/v1/reviewer/table-reviews/table-review-demo-1/publish", headers={"X-Role": "reviewer"}
    )
    assert published.status_code == 200
    assert published.json() == {
        "id": "table-review-demo-1",
        "cells": [
            {"row": 1, "column": 1, "role": "header", "text": "Kenar"},
            {"row": 1, "column": 2, "role": "header", "text": "Uzunluk"},
            {"row": 2, "column": 1, "role": "data", "text": "a"},
            {"row": 2, "column": 2, "role": "data", "text": "3"},
        ],
    }
    listed = client.get("/v1/student/documents/synthetic-geometry-01/tables", headers={"X-Role": "student"})
    assert listed.status_code == 200
    assert listed.json() == [published.json()]
    changed = demo_document.model_copy(deep=True).model_dump(mode="json")
    for block in changed["blocks"]:
        block["source"]["source_checksum"] = "d" * 64
    document_store.publish(changed)
    assert client.get("/v1/student/tables/table-review-demo-1", headers={"X-Role": "student"}).status_code == 404
    assert client.get("/v1/student/documents/synthetic-geometry-01/tables", headers={"X-Role": "student"}).json() == []
    reviewer_queue = client.get("/v1/reviewer/table-reviews", headers={"X-Role": "reviewer"})
    assert reviewer_queue.status_code == 200
    assert reviewer_queue.json()[0]["status"] == "published"


def test_teacher_can_supply_only_an_exceptional_cell_pronunciation():
    submission = {
        "id": "table-spoken-exception-1", "document_id": "synthetic-geometry-01",
        "schema_version": "visual-table-draft-v1", "kind": "table",
        "source": {"region_id": "region-1", "source_checksum": SAMPLE_CHECKSUM, "page": 1, "bbox": [72, 72, 300, 180]},
        "cells": [
            {"row": 1, "column": 1, "role": "header", "text": "Sembol", "confidence": 0.0},
            {"row": 2, "column": 1, "role": "data", "text": "A′", "confidence": 0.0},
        ],
        "confidence": 0.0, "publication_status": "requires-gold-and-teacher-review",
        "candidate_status": "candidate-vector-native-needs-gold-and-review",
    }
    created = client.post("/v1/admin/table-reviews", headers={"X-Role": "admin"}, json=submission)
    assert created.status_code == 201
    cells = created.json()["cells"]
    cells[1]["spoken_text"] = "A kümesinin tümleyeni"
    corrected = client.put("/v1/teacher/table-reviews/table-spoken-exception-1", headers={"X-Role": "teacher"}, json={
        "cells": cells, "reason": "Kaynak PDF ile istisna hücre okunuşu karşılaştırıldı.", "expected_revision": 1,
    })
    assert corrected.status_code == 200
    assert corrected.json()["cells"][1]["spoken_text"] == "A kümesinin tümleyeni"
    published = client.post("/v1/reviewer/table-reviews/table-spoken-exception-1/publish", headers={"X-Role": "reviewer"})
    assert published.status_code == 200
    assert published.json()["cells"][1]["spoken_text"] == "A kümesinin tümleyeni"


def test_table_pronunciation_rejects_markup_and_control_text():
    from app.table_review import TeacherTableCell
    from pydantic import ValidationError

    for spoken in ("<script>", "\\frac", "  ", "a\n\x00b"):
        with pytest.raises(ValidationError):
            TeacherTableCell(row=1, column=1, role="data", text="A", spoken_text=spoken)


def test_table_review_rejects_latex_and_non_vector_candidate():
    payload = {
        "id": "table-review-demo-2", "document_id": "synthetic-geometry-01",
        "schema_version": "visual-table-draft-v1", "kind": "table",
        "source": {"region_id": "grid", "source_checksum": SAMPLE_CHECKSUM, "page": 1, "bbox": [1, 1, 2, 2]},
        "cells": [{"row": 1, "column": 1, "role": "data", "text": r"\\frac{1}{2}", "confidence": 0.0}],
        "confidence": 0.0, "publication_status": "requires-gold-and-teacher-review",
        "candidate_status": "candidate-vector-native-needs-gold-and-review",
    }
    assert client.post("/v1/admin/table-reviews", headers={"X-Role": "admin"}, json=payload).status_code == 422
    payload["cells"][0]["text"] = "güvenli"
    payload["candidate_status"] = "candidate-visual-needs-review"
    assert client.post("/v1/admin/table-reviews", headers={"X-Role": "admin"}, json=payload).status_code == 422
