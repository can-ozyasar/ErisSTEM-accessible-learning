from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from .auth import Role, require_roles
from .job_store import DocumentStore, JobStore, ProcessingJob, make_session_factory


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


class Approval(BaseModel):
    reason: str = Field(min_length=5, max_length=500)
    expected_revision: int = Field(ge=1)


class TextCorrection(Approval):
    text: str = Field(min_length=1, max_length=10000)


class PageApproval(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class AuditEntry(BaseModel):
    at: datetime
    actor_role: Role
    action: str
    block_id: str | None = None
    detail: str


class QueueJobRequest(BaseModel):
    source_checksum: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str = Field(min_length=5, max_length=512)
    pipeline_version: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")

    @field_validator("source_relative_path")
    @classmethod
    def valid_source_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".pdf":
            raise ValueError("Kaynak yolu data/meb altında göreli bir PDF yolu olmalı")
        return path.as_posix()


class QueueJobResponse(BaseModel):
    id: str
    source_checksum: str
    source_relative_path: str
    pipeline_version: str
    status: str
    attempts: int
    created: bool


class TeacherDocumentSummary(BaseModel):
    id: str
    title: str
    published_revision: int
    review_required_count: int


class ReviewQueueItem(BaseModel):
    document_id: str
    block: Block


SAMPLE_CHECKSUM = hashlib.sha256(b"synthetic-geometry-page-v1").hexdigest()
demo_document = Document(
    id="synthetic-geometry-01",
    title="Sentetik geometri: dik üçgen",
    license_notice="Sentetik demo içeriğidir; MEB kaynağı değildir.",
    blocks=[
        Block(
            id="heading-1",
            kind="heading",
            reading_order=1,
            text="Dik üçgende Pisagor bağıntısı",
            status="published",
            source=SourceCoordinate(
                page=1,
                bbox=(72, 72, 500, 102),
                source_checksum=SAMPLE_CHECKSUM,
                extraction_step="pdf-text-layer",
            ),
            validation=Validation(
                schema_passed=True, render_score=1, source_agreement=1, confidence=1
            ),
        ),
        Block(
            id="paragraph-1",
            kind="paragraph",
            reading_order=2,
            text="Kenar uzunlukları a, b ve hipotenüs c olan dik üçgende ilişki aşağıdaki formülle verilir.",
            status="published",
            source=SourceCoordinate(
                page=1,
                bbox=(72, 116, 520, 154),
                source_checksum=SAMPLE_CHECKSUM,
                extraction_step="pdf-text-layer",
            ),
            validation=Validation(
                schema_passed=True, render_score=1, source_agreement=1, confidence=0.98
            ),
        ),
        Block(
            id="formula-1",
            kind="formula-display",
            reading_order=3,
            latex="a^2 + b^2 = c",
            mathml="<math><msup><mi>a</mi><mn>2</mn></msup><mo>+</mo><msup><mi>b</mi><mn>2</mn></msup><mo>=</mo><mi>c</mi></math>",
            status="review_required",
            source=SourceCoordinate(
                page=1,
                bbox=(180, 180, 420, 225),
                source_checksum=SAMPLE_CHECKSUM,
                extraction_step="formula-ocr-fallback",
            ),
            validation=Validation(
                schema_passed=True,
                render_score=0.63,
                source_agreement=0.51,
                confidence=0.42,
                reasons=["Hipotenüs üssü OCR sonucunda kayıp olabilir."],
            ),
        ),
    ],
)


any_role = Depends(require_roles(Role.STUDENT, Role.TEACHER, Role.REVIEWER, Role.ADMIN))
teacher_role = Depends(require_roles(Role.TEACHER, Role.REVIEWER, Role.ADMIN))
reviewer_role = Depends(require_roles(Role.REVIEWER, Role.ADMIN))
admin_role = Depends(require_roles(Role.ADMIN))


def get_document(document_id: str) -> Document:
    payload = document_store.get(document_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Belge bulunamadı")
    return Document.model_validate(payload)


def review_preview(document: Document, page: int) -> tuple[Path, dict[str, float]]:
    if not any(block.source.page == page for block in document.blocks):
        raise HTTPException(status_code=404, detail="Sayfa belgede bulunamadı")
    root = Path(os.getenv("DERIVED_ROOT", "data/derived")).resolve()
    directory = (root / "review-pages" / document.id).resolve()
    if not directory.is_relative_to(root):
        raise HTTPException(status_code=404, detail="Önizleme bulunamadı")
    image = directory / f"page-{page}.png"
    metadata = directory / "metadata.json"
    if not image.is_file() or not metadata.is_file():
        raise HTTPException(status_code=404, detail="Önizleme henüz üretilmedi")
    sizes = json.loads(metadata.read_text(encoding="utf-8"))
    if str(page) not in sizes:
        raise HTTPException(status_code=404, detail="Önizleme metadatası bulunamadı")
    return image, sizes[str(page)]


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
document_store = DocumentStore(job_store.sessions)
document_store.ensure(demo_document.model_dump(mode="json"))


def job_response(job: ProcessingJob, created: bool) -> QueueJobResponse:
    return QueueJobResponse(
        id=job.id,
        source_checksum=job.source_checksum,
        source_relative_path=job.source_relative_path,
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
    job, created = job_store.enqueue(
        request.source_checksum, request.source_relative_path, request.pipeline_version
    )
    return job_response(job, created)


@app.get("/v1/admin/processing-jobs", response_model=list[QueueJobResponse])
def list_processing_jobs(_: Role = admin_role):
    return [job_response(job, False) for job in job_store.list_recent()]


@app.get("/v1/student/documents/{document_id}", response_model=Document)
def read_published(document_id: str, _: Role = any_role):
    payload = document_store.get(document_id, published=True)
    if payload is None:
        raise HTTPException(status_code=404, detail="Belge bulunamadı")
    return Document.model_validate(payload)


@app.get("/v1/teacher/documents/{document_id}", response_model=Document)
def read_draft(document_id: str, _: Role = teacher_role):
    return get_document(document_id)


@app.get("/v1/teacher/documents/{document_id}/pages/{page}/preview")
def page_preview(document_id: str, page: int, _: Role = teacher_role):
    image, size = review_preview(get_document(document_id), page)
    return FileResponse(
        image,
        media_type="image/png",
        headers={"X-Pdf-Page-Width": str(size["width"]), "X-Pdf-Page-Height": str(size["height"])},
    )


@app.get("/v1/teacher/documents/{document_id}/pages/{page}/preview-metadata")
def page_preview_metadata(document_id: str, page: int, _: Role = teacher_role):
    _, size = review_preview(get_document(document_id), page)
    return size


@app.get("/v1/teacher/documents", response_model=list[TeacherDocumentSummary])
def list_teacher_documents(_: Role = teacher_role):
    documents = [Document.model_validate(payload) for payload in document_store.list_drafts()]
    return [
        TeacherDocumentSummary(
            id=item.id,
            title=item.title,
            published_revision=item.published_revision,
            review_required_count=sum(block.status == "review_required" for block in item.blocks),
        )
        for item in documents
    ]


@app.get("/v1/teacher/review-queue", response_model=list[ReviewQueueItem])
def review_queue(_: Role = teacher_role):
    items = []
    for payload in document_store.list_drafts():
        document = Document.model_validate(payload)
        items.extend(
            ReviewQueueItem(document_id=document.id, block=block)
            for block in document.blocks
            if block.status == "review_required"
        )
    return sorted(items, key=lambda item: item.block.validation.confidence)


@app.put("/v1/teacher/documents/{document_id}/blocks/{block_id}", response_model=Block)
def correct_block(document_id: str, block_id: str, update: Correction, role: Role = teacher_role):
    source = get_document(document_id)
    block = next((item for item in source.blocks if item.id == block_id), None)
    if block is None or block.kind != "formula-display":
        raise HTTPException(status_code=404, detail="Formül bulunamadı")
    if block.revision != update.expected_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="İçerik değişti; tekrar yükleyin"
        )
    validate_formula(update)
    block.latex, block.mathml = update.latex, update.mathml
    block.status = "approved"
    block.revision += 1
    block.validation = Validation(
        schema_passed=True,
        render_score=1,
        source_agreement=1,
        confidence=1,
        reasons=["Öğretmen düzeltmesi"],
    )
    document_store.save_draft(source.model_dump(mode="json"))
    document_store.add_audit(source.id, role, "formula_corrected", block.id, update.reason)
    return block


@app.post("/v1/teacher/documents/{document_id}/blocks/{block_id}/approve", response_model=Block)
def approve_text_block(
    document_id: str, block_id: str, approval: Approval, role: Role = teacher_role
):
    source = get_document(document_id)
    block = next((item for item in source.blocks if item.id == block_id), None)
    if block is None:
        raise HTTPException(status_code=404, detail="Blok bulunamadı")
    if block.kind == "formula-display":
        raise HTTPException(status_code=422, detail="Formül öğretmen düzeltme akışından geçmeli")
    if block.status != "review_required":
        raise HTTPException(status_code=409, detail="Blok denetim beklemiyor")
    if block.revision != approval.expected_revision:
        raise HTTPException(status_code=409, detail="İçerik değişti; tekrar yükleyin")
    block.status = "approved"
    block.revision += 1
    document_store.save_draft(source.model_dump(mode="json"))
    document_store.add_audit(source.id, role, "text_block_approved", block.id, approval.reason)
    return block


@app.put("/v1/teacher/documents/{document_id}/blocks/{block_id}/text", response_model=Block)
def correct_text_block(
    document_id: str, block_id: str, update: TextCorrection, role: Role = teacher_role
):
    source = get_document(document_id)
    block = next((item for item in source.blocks if item.id == block_id), None)
    if block is None or block.kind == "formula-display":
        raise HTTPException(status_code=404, detail="Metin bloğu bulunamadı")
    if block.revision != update.expected_revision:
        raise HTTPException(status_code=409, detail="İçerik değişti; tekrar yükleyin")
    block.text, block.status, block.revision = update.text.strip(), "approved", block.revision + 1
    block.validation = Validation(
        schema_passed=True,
        render_score=1,
        source_agreement=1,
        confidence=1,
        reasons=["Öğretmen metin düzeltmesi"],
    )
    document_store.save_draft(source.model_dump(mode="json"))
    document_store.add_audit(source.id, role, "text_corrected", block.id, update.reason)
    return block


@app.post("/v1/teacher/documents/{document_id}/pages/{page}/approve-text")
def approve_page_text(
    document_id: str, page: int, approval: PageApproval, role: Role = teacher_role
):
    """Öğretmenin kaynak sayfayı görerek yaptığı toplu metin onayı."""
    source = get_document(document_id)
    candidates = [
        block
        for block in source.blocks
        if block.source.page == page
        and block.kind != "formula-display"
        and block.status == "review_required"
    ]
    if not candidates:
        raise HTTPException(status_code=409, detail="Bu sayfada onay bekleyen metin yok")
    for block in candidates:
        block.status = "approved"
        block.revision += 1
    document_store.save_draft(source.model_dump(mode="json"))
    document_store.add_audit(
        source.id,
        role,
        "page_text_approved",
        None,
        f"page={page}; blocks={len(candidates)}; {approval.reason}",
    )
    return {"approved_count": len(candidates), "page": page}


@app.post("/v1/reviewer/documents/{document_id}/publish", response_model=Document)
def publish(document_id: str, role: Role = reviewer_role):
    source = get_document(document_id)
    pending = [b.id for b in source.blocks if b.status == "review_required"]
    if pending:
        raise HTTPException(
            status_code=422, detail={"message": "Denetim bekleyen öğeler var", "block_ids": pending}
        )
    for block in source.blocks:
        if block.status == "approved":
            block.status = "published"
    source.published_revision += 1
    document_store.publish(source.model_dump(mode="json"))
    document_store.add_audit(
        source.id, role, "document_published", None, f"revision={source.published_revision}"
    )
    return source


@app.get("/v1/audit", response_model=list[AuditEntry])
def audit(_: Role = reviewer_role):
    return [
        AuditEntry(
            at=item.at,
            actor_role=item.actor_role,
            action=item.action,
            block_id=item.block_id,
            detail=item.detail,
        )
        for item in document_store.audit()
    ]
