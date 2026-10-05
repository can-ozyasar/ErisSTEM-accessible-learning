from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .job_store import JobStore, ProcessingJob, make_session_factory


class Role(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class SourceCoordinate(BaseModel):
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float]
    source_checksum: str = Field(min_length=64, max_length=64)
    extraction_step: str

    @field_validator("bbox")
    @classmethod
    def valid_box(cls, value: tuple[float, float, float, float]):
        x0, y0, x1, y1 = value
        if x0 >= x1 or y0 >= y1:
            raise ValueError("bbox must have positive area")
        return value


class Validation(BaseModel):
    schema_passed: bool
    render_score: float = Field(ge=0, le=1)
    source_agreement: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = []


class Block(BaseModel):
    id: str
    kind: Literal["heading", "paragraph", "formula-display"]
    reading_order: int
    source: SourceCoordinate
    validation: Validation
    text: str | None = None
    latex: str | None = None
    mathml: str | None = None
    status: Literal["published", "review_required", "approved"]
    revision: int = 1


class Document(BaseModel):
    id: str
    title: str
    license_notice: str
    published_revision: int = 1
    blocks: list[Block]


class Correction(BaseModel):
    latex: str = Field(min_length=1, max_length=1000)
    mathml: str = Field(min_length=1, max_length=5000)
    reason: str = Field(min_length=5, max_length=500)
    expected_revision: int = Field(ge=1)


class AuditEntry(BaseModel):
    at: datetime
    actor_role: Role
    action: str
    block_id: str | None = None
    detail: str


class QueueJobRequest(BaseModel):
    source_checksum: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    pipeline_version: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")


class QueueJobResponse(BaseModel):
    id: str
    source_checksum: str
    pipeline_version: str
    status: str
    attempts: int
    created: bool


SAMPLE_CHECKSUM = hashlib.sha256(b"synthetic-geometry-page-v1").hexdigest()
document = Document(
    id="synthetic-geometry-01",
    title="Sentetik geometri: dik üçgen",
    license_notice="Sentetik demo içeriğidir; MEB kaynağı değildir.",
    blocks=[
        Block(id="heading-1", kind="heading", reading_order=1, text="Dik üçgende Pisagor bağıntısı", status="published", source=SourceCoordinate(page=1, bbox=(72, 72, 500, 102), source_checksum=SAMPLE_CHECKSUM, extraction_step="pdf-text-layer"), validation=Validation(schema_passed=True, render_score=1, source_agreement=1, confidence=1)),
        Block(id="paragraph-1", kind="paragraph", reading_order=2, text="Kenar uzunlukları a, b ve hipotenüs c olan dik üçgende ilişki aşağıdaki formülle verilir.", status="published", source=SourceCoordinate(page=1, bbox=(72, 116, 520, 154), source_checksum=SAMPLE_CHECKSUM, extraction_step="pdf-text-layer"), validation=Validation(schema_passed=True, render_score=1, source_agreement=1, confidence=.98)),
        Block(id="formula-1", kind="formula-display", reading_order=3, latex="a^2 + b^2 = c", mathml="<math><msup><mi>a</mi><mn>2</mn></msup><mo>+</mo><msup><mi>b</mi><mn>2</mn></msup><mo>=</mo><mi>c</mi></math>", status="review_required", source=SourceCoordinate(page=1, bbox=(180, 180, 420, 225), source_checksum=SAMPLE_CHECKSUM, extraction_step="formula-ocr-fallback"), validation=Validation(schema_passed=True, render_score=.63, source_agreement=.51, confidence=.42, reasons=["Hipotenüs üssü OCR sonucunda kayıp olabilir."])),
    ],
)
audit_log: list[AuditEntry] = []


def require_roles(*roles: Role):
    def dependency(x_role: Annotated[str | None, Header()] = None) -> Role:
        try:
            role = Role(x_role or "student")
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Geçersiz rol") from exc
        if role not in roles:
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
        return role
    return dependency


any_role = Depends(require_roles(Role.STUDENT, Role.TEACHER, Role.REVIEWER, Role.ADMIN))
teacher_role = Depends(require_roles(Role.TEACHER, Role.REVIEWER, Role.ADMIN))
reviewer_role = Depends(require_roles(Role.REVIEWER, Role.ADMIN))
admin_role = Depends(require_roles(Role.ADMIN))


def get_document(document_id: str) -> Document:
    if document_id != document.id:
        raise HTTPException(status_code=404, detail="Belge bulunamadı")
    return document


def validate_formula(update: Correction) -> None:
    if not re.fullmatch(r"[a-zA-Z0-9^_+\-=/(){}\\ ]+", update.latex):
        raise HTTPException(status_code=422, detail="LaTeX izinli sembol kümesinin dışında")
    if "<math" not in update.mathml or "</math>" not in update.mathml:
        raise HTTPException(status_code=422, detail="MathML kök math öğesi içermeli")
    if "<script" in update.mathml.lower():
        raise HTTPException(status_code=422, detail="MathML güvenli değil")


app = FastAPI(title="ErişSTEM API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "X-Role"],
)
job_store = JobStore(make_session_factory())


def job_response(job: ProcessingJob, created: bool) -> QueueJobResponse:
    return QueueJobResponse(
        id=job.id,
        source_checksum=job.source_checksum,
        pipeline_version=job.pipeline_version,
        status=job.status,
        attempts=job.attempts,
        created=created,
    )


@app.get("/health")
def health(_: Role = any_role):
    return {"status": "ok"}


@app.post("/v1/admin/processing-jobs", response_model=QueueJobResponse, status_code=201)
def queue_processing_job(request: QueueJobRequest, _: Role = admin_role):
    job, created = job_store.enqueue(request.source_checksum, request.pipeline_version)
    return job_response(job, created)


@app.get("/v1/admin/processing-jobs", response_model=list[QueueJobResponse])
def list_processing_jobs(_: Role = admin_role):
    return [job_response(job, False) for job in job_store.list_recent()]


@app.get("/v1/student/documents/{document_id}", response_model=Document)
def read_published(document_id: str, _: Role = any_role):
    source = get_document(document_id)
    return source.model_copy(update={"blocks": [b for b in source.blocks if b.status == "published"]})


@app.get("/v1/teacher/documents/{document_id}", response_model=Document)
def read_draft(document_id: str, _: Role = teacher_role):
    return get_document(document_id)


@app.get("/v1/teacher/review-queue", response_model=list[Block])
def review_queue(_: Role = teacher_role):
    return sorted((b for b in document.blocks if b.status == "review_required"), key=lambda b: b.validation.confidence)


@app.put("/v1/teacher/documents/{document_id}/blocks/{block_id}", response_model=Block)
def correct_block(document_id: str, block_id: str, update: Correction, role: Role = teacher_role):
    source = get_document(document_id)
    block = next((item for item in source.blocks if item.id == block_id), None)
    if block is None or block.kind != "formula-display":
        raise HTTPException(status_code=404, detail="Formül bulunamadı")
    if block.revision != update.expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="İçerik değişti; tekrar yükleyin")
    validate_formula(update)
    block.latex, block.mathml = update.latex, update.mathml
    block.status = "approved"
    block.revision += 1
    block.validation = Validation(schema_passed=True, render_score=1, source_agreement=1, confidence=1, reasons=["Öğretmen düzeltmesi"])
    audit_log.append(AuditEntry(at=datetime.now(UTC), actor_role=role, action="formula_corrected", block_id=block.id, detail=update.reason))
    return block


@app.post("/v1/reviewer/documents/{document_id}/publish", response_model=Document)
def publish(document_id: str, role: Role = reviewer_role):
    source = get_document(document_id)
    pending = [b.id for b in source.blocks if b.status == "review_required"]
    if pending:
        raise HTTPException(status_code=422, detail={"message": "Denetim bekleyen öğeler var", "block_ids": pending})
    for block in source.blocks:
        if block.status == "approved":
            block.status = "published"
    source.published_revision += 1
    audit_log.append(AuditEntry(at=datetime.now(UTC), actor_role=role, action="document_published", detail=f"revision={source.published_revision}"))
    return source


@app.get("/v1/audit", response_model=list[AuditEntry])
def audit(_: Role = reviewer_role):
    return audit_log
