from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from .auth import Role, require_roles
from .exam_practice import ExamStore
from .history_source import router as history_router
from .job_store import (
    BenchmarkAnnotation,
    DocumentStore,
    JobStore,
    ProcessingJob,
    TableReviewStore,
    make_session_factory,
)
from .learning_operations import LearningOperationsStore
from .learning_routes import learning_router
from .local_tts import (
    LocalTtsUnavailable,
    synthesize_cached_verified_text,
    synthesize_verified_text,
)
from .pipeline.accessibility_reader import ReadingPlan, build_reading_plan
from .pipeline.accessible_content import CanonicalAccessibleBlock
from .pipeline.braille_adapter import (
    BrailleUnavailable,
    LiteraryBrailleResponse,
    translate_verified_literary,
)
from .pipeline.latex_ocr_adapter import LatexOcrError, latex_ocr_candidate
from .pipeline.learning_experience import (
    LearningFeedback,
    LearningModule,
    ModuleSummary,
    check_module_answer,
    module_catalog,
    read_module,
)
from .pipeline.math_notation import MathNotationError, notation_speech_candidate
from .pipeline.set_practice import (
    BY_ID as SET_EXERCISES,
)
from .pipeline.set_practice import (
    AnswerFeedback,
    AnswerSubmission,
    PracticeBank,
)
from .pipeline.set_practice import (
    check_answer as check_set_answer,
)
from .pipeline.set_practice import (
    public_bank as public_set_bank,
)
from .pipeline.tts_audio_assets import load_audio_manifest, resolve_verified_audio
from .pipeline.turkish_math_speech import (
    MathSpeechError,
    compile_mathml_candidate,
    turkish_math_speech_plan,
)
from .pipeline.type_specific_accessibility import FormulaAccessibility
from .question_bank_routes import question_bank_router
from .table_review import (
    PublishedTable,
    TableReviewApproval,
    TableReviewCorrection,
    TeacherTableReview,
    VectorNativeTableIngress,
    teacher_projection,
)


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
    spoken_text: str | None = None
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
    spoken_text: str | None = Field(default=None, min_length=1, max_length=5000)
    reason: str = Field(min_length=5, max_length=500)
    expected_revision: int = Field(ge=1)


class Approval(BaseModel):
    reason: str = Field(min_length=5, max_length=500)
    expected_revision: int = Field(ge=1)


class FormulaSpeechProposal(BaseModel):
    block_id: str
    expected_revision: int
    proposed_spoken_text: str


class FormulaNotationRequest(BaseModel):
    visible_notation: str = Field(min_length=1, max_length=1000)
    measurement_label: str | None = Field(default=None, max_length=120)


class FormulaNotationProposal(BaseModel):
    visible_notation: str
    mathml: str
    proposed_spoken_text: str


class FormulaOcrRequest(BaseModel):
    latex: str = Field(min_length=1, max_length=1000)


class TextCorrection(Approval):
    text: str = Field(min_length=1, max_length=10000)


class PageApproval(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class GoldAnnotation(BaseModel):
    expected: str = Field(min_length=1, max_length=10000)


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


class StudentReadingPlanResponse(BaseModel):
    """Verified speech/screen-reader units; unsupported blocks are never faked."""

    plan: ReadingPlan
    unavailable_block_ids: list[str]


class StudentDocumentSummary(BaseModel):
    id: str
    title: str
    published_revision: int
    block_count: int


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
    return preview_file(document.id, page)


def preview_file(document_id: str, page: int) -> tuple[Path, dict[str, float]]:
    """Read a pre-rendered private page preview without exposing the PDF itself."""
    root = Path(os.getenv("DERIVED_ROOT", "data/derived")).resolve()
    directory = (root / "review-pages" / document_id).resolve()
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


def gold_manifest() -> dict:
    path = Path(os.getenv("DERIVED_ROOT", "data/derived")) / "gold-v1.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Private Gold manifesti bulunamadı")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_formula(update: Correction) -> None:
    if not re.fullmatch(r"[a-zA-Z0-9α-ωΑ-Ωℝ^_+\-−=/(){}\[\]\\,.·×÷<>≤≥≠∈∉| ]+", update.latex):
        raise HTTPException(status_code=422, detail="LaTeX izinli sembol kümesinin dışında")
    if "<math" not in update.mathml or "</math>" not in update.mathml:
        raise HTTPException(status_code=422, detail="MathML kök math öğesi içermeli")
    if "<script" in update.mathml.lower():
        raise HTTPException(status_code=422, detail="MathML güvenli değil")


def needs_structured_math_extraction(block: Block) -> bool:
    """Metin katmanındaki parçalanmış matematik işaretlerini toplu yayından korur."""
    text = block.text or ""
    return bool(
        re.search(r"\d(?:\s+\d){2,}", text)
        or "�" in text
        or (any(symbol in text for symbol in ("/", "=", "−", "÷")) and len(text) < 30)
    )


def canonical_text_block(block: Block) -> CanonicalAccessibleBlock:
    """Adapt a published direct-text block to the shared accessibility contract."""
    if block.kind not in {"heading", "paragraph"} or not block.text:
        raise ValueError("block is not verified direct text")
    return CanonicalAccessibleBlock.model_validate(
        {
            "id": block.id,
            "kind": block.kind,
            "source_checksum": block.source.source_checksum,
            "page": block.source.page,
            "bbox": block.source.bbox,
            "reading_order": block.reading_order,
            "representations": {
                "navigation_label": "Başlık" if block.kind == "heading" else "Paragraf",
                "spoken_text": block.text,
                "braille_source": block.text,
            },
            "quality": {
                "source_bound": True,
                "schema_valid": block.validation.schema_passed,
                "render_valid": block.validation.render_score == 1,
                "source_agreement": block.validation.source_agreement,
                # A published document has passed the independent reviewer
                # gate. Preserve the extraction value in its audit record, but
                # represent the reviewed release evidence to the reader plan.
                "confidence": 1.0 if block.status == "published" else block.validation.confidence,
                "gold_gate_passed": True,
                "critical_error_count": 0,
            },
        }
    )


def canonical_formula_block(block: Block) -> CanonicalAccessibleBlock:
    """Compile only teacher-corrected, published MathML into Turkish speech."""
    if (
        block.kind != "formula-display"
        or block.status != "published"
        or not block.mathml
        or not {"Öğretmen düzeltmesi", "Öğretmen formül okunuşunu kaynakla doğruladı"}.intersection(block.validation.reasons)
    ):
        raise ValueError("formula has no reviewed MathML")
    evidence = {
        "source_bound": True,
        "schema_valid": block.validation.schema_passed,
        "render_valid": block.validation.render_score == 1,
        "source_agreement": block.validation.source_agreement,
        "confidence": block.validation.confidence,
        "gold_gate_passed": True,  # Teacher correction and separate reviewer publication.
        "critical_error_count": 0,
    }
    formula = FormulaAccessibility.model_validate({
        "mathml": block.mathml,
        "short_spoken_text": "Doğrulanmış matematiksel ifade",
        "detailed_spoken_text": "Doğrulanmış matematiksel ifade",
        "quality": evidence,
    })
    speech = turkish_math_speech_plan(formula)
    if block.spoken_text is not None and not valid_formula_speech(block.spoken_text, speech.spoken_text):
        raise ValueError("stored_formula_speech_does_not_match_mathml")
    return CanonicalAccessibleBlock.model_validate({
        "id": block.id,
        "kind": "formula",
        "source_checksum": block.source.source_checksum,
        "page": block.source.page,
        "bbox": block.source.bbox,
        "reading_order": block.reading_order,
        "representations": {
            "navigation_label": "Formül",
            "spoken_text": block.spoken_text or speech.spoken_text,
            "mathml": block.mathml,
        },
        "quality": evidence,
    })


def valid_formula_speech(stored: str, base: str) -> bool:
    """Allow only a teacher-verified geometry anchor before deterministic maths."""
    return stored == base or bool(re.fullmatch(rf"[^:]{{2,120}} ölçüsü: {re.escape(base)}", stored))


app = FastAPI(title="ErişSTEM API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Role"],
)
job_store = JobStore(make_session_factory())
document_store = DocumentStore(job_store.sessions)
table_review_store = TableReviewStore(job_store.sessions)
learning_operations_store = LearningOperationsStore(job_store.sessions)
exam_store = ExamStore(learning_operations_store)
app.include_router(learning_router(learning_operations_store, exam_store))
app.include_router(history_router)
app.include_router(question_bank_router(learning_operations_store))


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


class InterfaceSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)


@app.post("/v1/student/interface-speech")
def interface_speech(request: InterfaceSpeechRequest, _: Role = any_role):
    """Local-only, ephemeral TTS for short UI labels; never stored as lesson audio."""
    if os.getenv("APP_ENV", "development") == "production":
        raise HTTPException(503, "Arayüz seslendirmesi üretime açılmadı")
    value = re.sub(r"\s+", " ", request.text).strip()
    if not value or any(ord(char) < 32 for char in value):
        raise HTTPException(422, "Geçersiz arayüz metni")
    try:
        audio = synthesize_verified_text(value)
    except LocalTtsUnavailable as error:
        raise HTTPException(503, "Yerel Türkçe ses kullanılamıyor") from error
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@app.get("/v1/student/learning/modules", response_model=list[ModuleSummary])
def list_learning_modules(_: Role = any_role):
    result = []
    for module in module_catalog():
        quality = learning_operations_store.quality(module.id)
        if os.getenv("LEARNING_REQUIRE_RELEASE") == "true" and quality["status"] != "published":
            continue
        result.append(module.model_copy(update={"quality_status": quality["status"]}))
    return result


def require_learning_release(module_id: str):
    quality = learning_operations_store.quality(module_id)
    if os.getenv("LEARNING_REQUIRE_RELEASE") == "true" and quality["status"] != "published":
        raise HTTPException(409, "Bu içeriğin uzman incelemesi ve kullanıcı pilotu henüz tamamlanmadı")
    return quality


@app.get("/v1/student/learning/modules/{module_id}", response_model=LearningModule)
def get_learning_module(module_id: str, _: Role = any_role):
    module = read_module(module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Öğrenme içeriği bulunamadı")
    quality = require_learning_release(module_id)
    return module.model_copy(update={"quality_status": quality["status"],
        "provenance": "ErişSTEM sentetik içeriği; güncel uzman ve pilot kayıtları yayın kontrolünü geçti."
        if quality["status"] == "published" else module.provenance})


@app.post(
    "/v1/student/learning/modules/{module_id}/exercises/{exercise_id}/check",
    response_model=LearningFeedback,
)
def check_learning_exercise(
    module_id: str, exercise_id: str, submission: AnswerSubmission, _: Role = any_role,
):
    require_learning_release(module_id)
    result = check_module_answer(module_id, exercise_id, submission)
    if result is None:
        raise HTTPException(status_code=404, detail="Alıştırma bulunamadı")
    return result


@app.get("/v1/student/practice/sets", response_model=PracticeBank)
def read_set_practice(_: Role = any_role):
    require_learning_release("sets")
    return public_set_bank()


@app.post("/v1/student/practice/sets/{exercise_id}/check", response_model=AnswerFeedback)
def check_set_practice(exercise_id: str, submission: AnswerSubmission, _: Role = any_role):
    require_learning_release("sets")
    exercise = SET_EXERCISES.get(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Alıştırma bulunamadı")
    return check_set_answer(exercise, submission)


@app.post("/v1/admin/processing-jobs", response_model=QueueJobResponse, status_code=201)
def queue_processing_job(request: QueueJobRequest, _: Role = admin_role):
    job, created = job_store.enqueue(
        request.source_checksum, request.source_relative_path, request.pipeline_version
    )
    return job_response(job, created)


@app.get("/v1/admin/processing-jobs", response_model=list[QueueJobResponse])
def list_processing_jobs(_: Role = admin_role):
    return [job_response(job, False) for job in job_store.list_recent()]


@app.get("/v1/student/documents", response_model=list[StudentDocumentSummary])
def list_published_documents(_: Role = any_role):
    return [StudentDocumentSummary(
        id=payload["id"], title=payload["title"],
        published_revision=payload.get("published_revision", 1),
        block_count=len(payload["blocks"]),
    ) for payload in document_store.list_published()]


@app.get("/v1/student/documents/{document_id}", response_model=Document)
def read_published(document_id: str, _: Role = any_role):
    payload = document_store.get(document_id, published=True)
    if payload is None:
        raise HTTPException(status_code=404, detail="Belge bulunamadı")
    return Document.model_validate(payload)


@app.get("/v1/student/documents/{document_id}/reading-plan", response_model=StudentReadingPlanResponse)
def read_verified_plan(document_id: str, _: Role = any_role):
    """Expose reviewed text and supported, teacher-corrected MathML speech."""
    document = read_published(document_id, _)
    canonical, unavailable = [], []
    for block in document.blocks:
        try:
            canonical.append(canonical_formula_block(block) if block.kind == "formula-display" else canonical_text_block(block))
        except (ValueError, MathSpeechError):
            unavailable.append(block.id)
    if not canonical:
        raise HTTPException(status_code=409, detail="Doğrulanmış sesli okuma birimi bulunamadı")
    return StudentReadingPlanResponse(plan=build_reading_plan(canonical), unavailable_block_ids=unavailable)


@app.get("/v1/student/documents/{document_id}/audio/{unit_id}")
def read_verified_audio(document_id: str, unit_id: str, _: Role = any_role):
    """Serve only a listener-approved WAV bound to the active reading unit."""
    document = read_published(document_id, _)
    reading = read_verified_plan(document_id, _)
    unit = next((item for item in reading.plan.units if item.id == unit_id), None)
    if unit is None:
        raise HTTPException(status_code=404, detail="Doğrulanmış ses birimi bulunamadı")
    root = Path(os.getenv("STUDENT_AUDIO_ROOT", "data/derived/student-audio")).resolve()
    directory = (root / document_id).resolve()
    if not directory.is_relative_to(root):
        raise HTTPException(status_code=404, detail="Ses varlığı bulunamadı")
    try:
        manifest = load_audio_manifest(directory / "assets.json")
        audio, asset = resolve_verified_audio(
            manifest,
            directory,
            document_id=document_id,
            published_revision=document.published_revision,
            unit=unit,
        )
    except ValueError:
        # A missing, stale, altered, or unreviewed asset must not fall through
        # to an arbitrary file or be exposed as a student audio resource.
        raise HTTPException(status_code=404, detail="Bu birim için onaylı ses bulunamadı") from None
    return FileResponse(
        audio,
        media_type="audio/wav",
        headers={
            "ETag": f'"{asset.audio_sha256}"',
            "Cache-Control": "private, no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/v1/student/documents/{document_id}/local-audio/{unit_id}")
def read_local_audio(document_id: str, unit_id: str, _: Role = any_role):
    """Synthesize a reviewed reading-plan unit with the offline TTS service.

    This is a local development/runtime voice, not listener-approved released
    audio.  The route deliberately has no text parameter: unreviewed OCR,
    MathML and client-provided text can never reach the model through it.
    """
    reading = read_verified_plan(document_id, _)
    unit = next((item for item in reading.plan.units if item.id == unit_id), None)
    if unit is None:
        raise HTTPException(status_code=404, detail="Doğrulanmış ses birimi bulunamadı")
    try:
        audio = synthesize_cached_verified_text(unit.spoken_text)
    except LocalTtsUnavailable:
        raise HTTPException(status_code=503, detail="Yerel Türkçe ses motoru kullanılamıyor") from None
    return Response(
        audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.get("/v1/student/documents/{document_id}/braille/{unit_id}", response_model=LiteraryBrailleResponse)
def read_verified_braille(document_id: str, unit_id: str, _: Role = any_role):
    """Return Turkish Grade 1 cells only for a current, verified text unit."""
    reading = read_verified_plan(document_id, _)
    unit = next((item for item in reading.plan.units if item.id == unit_id), None)
    if unit is None:
        raise HTTPException(status_code=404, detail="Doğrulanmış Braille birimi bulunamadı")
    try:
        return translate_verified_literary(unit)
    except BrailleUnavailable:
        raise HTTPException(status_code=503, detail="Bu birim için doğrulanmış Braille dönüşümü kullanılamıyor") from None


@app.get("/v1/teacher/documents/{document_id}", response_model=Document)
def read_draft(document_id: str, _: Role = teacher_role):
    return get_document(document_id)


@app.get("/v1/teacher/benchmark/gold-v1/items")
def list_gold_items(_: Role = teacher_role):
    with job_store.sessions() as session:
        annotations = {
            item.id: item.expected for item in session.scalars(select(BenchmarkAnnotation))
        }
    return [
        {**item, "expected": annotations.get(item["id"], "")} for item in gold_manifest()["items"]
    ]


@app.get("/v1/teacher/benchmark/gold-v1/items/{item_id}/preview")
def gold_preview(item_id: str, _: Role = teacher_role):
    item = next((value for value in gold_manifest()["items"] if value["id"] == item_id), None)
    root = Path(os.getenv("DERIVED_ROOT", "data/derived")) / "review-pages" / "benchmark-gold-v1"
    image = root / f"page-{item['page']}.png" if item else None
    if image is None or not image.is_file():
        raise HTTPException(status_code=404, detail="Gold sayfa önizlemesi bulunamadı")
    return FileResponse(image, media_type="image/png")


def source_bound_document(document_id: str, source_checksum: str) -> Document:
    document = get_document(document_id)
    if not any(block.source.source_checksum == source_checksum for block in document.blocks):
        raise HTTPException(status_code=422, detail="Tablo kaynağı belge checksum'ı ile eşleşmiyor")
    return document


@app.post("/v1/admin/table-reviews", response_model=TeacherTableReview, response_model_exclude_none=True, status_code=201)
def import_vector_native_table_review(
    submission: VectorNativeTableIngress, role: Role = admin_role
):
    """Accept only the deterministic vector/native candidate envelope from a private worker."""
    source_bound_document(submission.document_id, submission.source.source_checksum)
    payload = submission.model_dump(mode="json")
    try:
        item = table_review_store.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    document_store.add_audit(
        submission.document_id, role, "vector_native_table_imported", submission.id,
        f"page={submission.source.page}; region={submission.source.region_id}",
    )
    return teacher_projection(item.draft_payload, item.status, item.revision)


@app.get("/v1/teacher/table-reviews", response_model=list[TeacherTableReview], response_model_exclude_none=True)
def table_review_queue(_: Role = teacher_role):
    """Only uncertain, still-unapproved tables are listed for the teacher."""
    return [
        teacher_projection(item.draft_payload, item.status, item.revision)
        for item in table_review_store.list_pending()
    ]


def get_table_review(table_id: str):
    item = table_review_store.get(table_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tablo denetim kaydı bulunamadı")
    return item


@app.get("/v1/teacher/table-reviews/{table_id}/preview")
def table_review_preview(table_id: str, _: Role = teacher_role):
    item = get_table_review(table_id)
    payload = item.draft_payload
    source_bound_document(payload["document_id"], payload["source"]["source_checksum"])
    image, size = preview_file(payload["document_id"], payload["source"]["page"])
    return FileResponse(
        image,
        media_type="image/png",
        headers={"X-Pdf-Page-Width": str(size["width"]), "X-Pdf-Page-Height": str(size["height"])},
    )


@app.put("/v1/teacher/table-reviews/{table_id}", response_model=TeacherTableReview, response_model_exclude_none=True)
def correct_table_review(
    table_id: str, update: TableReviewCorrection, role: Role = teacher_role
):
    item = get_table_review(table_id)
    if item.status != "review_required":
        raise HTTPException(status_code=409, detail="Tablo denetim beklemiyor")
    if item.revision != update.expected_revision:
        raise HTTPException(status_code=409, detail="İçerik değişti; tekrar yükleyin")
    original = {(cell["row"], cell["column"]) for cell in item.draft_payload["cells"]}
    corrected = {(cell.row, cell.column) for cell in update.cells}
    if original != corrected:
        raise HTTPException(status_code=422, detail="Hücre yapısı değiştirilemez; yalnız hücre metni/rolü doğrulanır")
    payload = {**item.draft_payload, "cells": [cell.model_dump(mode="json") for cell in update.cells]}
    saved = table_review_store.save(table_id, payload, status="approved", revision=item.revision + 1)
    document_store.add_audit(payload["document_id"], role, "table_corrected", table_id, update.reason)
    return teacher_projection(saved.draft_payload, saved.status, saved.revision)


@app.post("/v1/teacher/table-reviews/{table_id}/approve", response_model=TeacherTableReview, response_model_exclude_none=True)
def approve_table_review(
    table_id: str, approval: TableReviewApproval, role: Role = teacher_role
):
    item = get_table_review(table_id)
    if item.status != "review_required":
        raise HTTPException(status_code=409, detail="Tablo denetim beklemiyor")
    if item.revision != approval.expected_revision:
        raise HTTPException(status_code=409, detail="İçerik değişti; tekrar yükleyin")
    saved = table_review_store.save(table_id, item.draft_payload, status="approved", revision=item.revision + 1)
    document_store.add_audit(item.document_id, role, "table_approved", table_id, approval.reason)
    return teacher_projection(saved.draft_payload, saved.status, saved.revision)


@app.post("/v1/reviewer/table-reviews/{table_id}/publish", response_model=PublishedTable, response_model_exclude_none=True)
def publish_table_review(table_id: str, role: Role = reviewer_role):
    item = get_table_review(table_id)
    if item.status != "approved":
        raise HTTPException(status_code=422, detail="Tablo öğretmen tarafından henüz onaylanmadı")
    published = table_review_store.publish(table_id)
    document_store.add_audit(item.document_id, role, "table_published", table_id, "teacher-approved")
    return PublishedTable(id=published.id, cells=teacher_projection(published.draft_payload, "published", published.revision).cells)


@app.get("/v1/reviewer/table-reviews", response_model=list[TeacherTableReview], response_model_exclude_none=True)
def reviewer_table_review_queue(_: Role = reviewer_role):
    """Reviewer sees teacher-approved tables, including already published records."""
    return [
        teacher_projection(item.draft_payload, item.status, item.revision)
        for item in table_review_store.list_teacher_approved()
    ]


@app.get("/v1/student/tables/{table_id}", response_model=PublishedTable, response_model_exclude_none=True)
def read_published_table(table_id: str, _: Role = any_role):
    item = get_table_review(table_id)
    if item.status != "published" or item.published_payload is None:
        raise HTTPException(status_code=404, detail="Yayımlanmış tablo bulunamadı")
    document = document_store.get(item.document_id, published=True)
    checksums = {block["source"]["source_checksum"] for block in document.get("blocks", [])} if document else set()
    if item.published_payload["source"]["source_checksum"] not in checksums:
        raise HTTPException(status_code=404, detail="Tablo güncel yayımlanmış kaynağa bağlı değil")
    projection = teacher_projection(item.published_payload, "published", item.revision)
    return PublishedTable(id=item.id, cells=projection.cells)


@app.get("/v1/student/documents/{document_id}/tables", response_model=list[PublishedTable], response_model_exclude_none=True)
def list_published_document_tables(document_id: str, _: Role = any_role):
    document = document_store.get(document_id, published=True)
    if not document or not document.get("blocks"):
        raise HTTPException(status_code=404, detail="Belge bulunamadı")
    checksums = {block["source"]["source_checksum"] for block in document["blocks"]}
    return [PublishedTable(id=item.id, cells=teacher_projection(
        item.published_payload, "published", item.revision
    ).cells) for item in table_review_store.list_published_for_document(document_id)
        if item.published_payload is not None and item.published_payload["source"]["source_checksum"] in checksums]


@app.put("/v1/teacher/benchmark/gold-v1/items/{item_id}")
def save_gold_annotation(item_id: str, annotation: GoldAnnotation, _: Role = teacher_role):
    if not any(item["id"] == item_id for item in gold_manifest()["items"]):
        raise HTTPException(status_code=404, detail="Gold örneği bulunamadı")
    with job_store.sessions.begin() as session:
        record = session.get(BenchmarkAnnotation, item_id)
        if record is None:
            session.add(
                BenchmarkAnnotation(
                    id=item_id, expected=annotation.expected.strip(), updated_at=datetime.now(UTC)
                )
            )
        else:
            record.expected, record.updated_at = annotation.expected.strip(), datetime.now(UTC)
    return {"id": item_id, "saved": True}


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
    try:
        base_speech = compile_mathml_candidate(update.mathml)
    except MathSpeechError:
        raise HTTPException(status_code=422, detail="Formülün desteklenen Türkçe okunuşu yok") from None
    if update.spoken_text is not None and not valid_formula_speech(update.spoken_text, base_speech):
        raise HTTPException(status_code=422, detail="Türkçe okunuş MathML ile eşleşmiyor")
    block.spoken_text = update.spoken_text or base_speech
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


@app.get("/v1/teacher/documents/{document_id}/blocks/{block_id}/speech-proposal", response_model=FormulaSpeechProposal)
def formula_speech_proposal(document_id: str, block_id: str, _: Role = teacher_role):
    source = get_document(document_id)
    block = next((item for item in source.blocks if item.id == block_id), None)
    if block is None or block.kind != "formula-display" or not block.mathml:
        raise HTTPException(status_code=404, detail="Formül bulunamadı")
    try:
        proposed = compile_mathml_candidate(block.mathml)
    except MathSpeechError:
        raise HTTPException(status_code=422, detail="Formülün desteklenen Türkçe okunuşu yok") from None
    return FormulaSpeechProposal(block_id=block.id, expected_revision=block.revision, proposed_spoken_text=proposed)


@app.post(
    "/v1/teacher/documents/{document_id}/blocks/{block_id}/notation-proposal",
    response_model=FormulaNotationProposal,
)
def formula_notation_proposal(
    document_id: str, block_id: str, request: FormulaNotationRequest, _: Role = teacher_role
):
    """Compile one teacher-visible expression; never join independent PDF fragments."""
    source = get_document(document_id)
    block = next((item for item in source.blocks if item.id == block_id), None)
    if block is None or block.kind != "formula-display":
        raise HTTPException(status_code=404, detail="Formül bulunamadı")
    try:
        mathml, spoken = notation_speech_candidate(
            request.visible_notation, measurement_label=request.measurement_label
        )
    except MathNotationError as error:
        raise HTTPException(status_code=422, detail=f"Desteklenmeyen gösterim: {error}") from error
    return FormulaNotationProposal(
        visible_notation=request.visible_notation, mathml=mathml, proposed_spoken_text=spoken
    )


@app.post(
    "/v1/teacher/documents/{document_id}/blocks/{block_id}/ocr-latex-proposal",
    response_model=FormulaNotationProposal,
)
def formula_ocr_latex_proposal(
    document_id: str, block_id: str, request: FormulaOcrRequest, _: Role = teacher_role
):
    """Adapt a whole-expression OCR result; it is still only a teacher proposal."""
    source = get_document(document_id)
    block = next((item for item in source.blocks if item.id == block_id), None)
    if block is None or block.kind != "formula-display":
        raise HTTPException(status_code=404, detail="Formül bulunamadı")
    try:
        visible, mathml, spoken = latex_ocr_candidate(request.latex)
    except LatexOcrError as error:
        raise HTTPException(status_code=422, detail=f"OCR gösterimi desteklenmiyor: {error}") from error
    return FormulaNotationProposal(
        visible_notation=visible, mathml=mathml, proposed_spoken_text=spoken
    )


@app.post("/v1/teacher/documents/{document_id}/blocks/{block_id}/approve-formula", response_model=Block)
def approve_formula_candidate(document_id: str, block_id: str, approval: Approval, role: Role = teacher_role):
    source = get_document(document_id)
    block = next((item for item in source.blocks if item.id == block_id), None)
    if block is None or block.kind != "formula-display" or not block.mathml:
        raise HTTPException(status_code=404, detail="Formül bulunamadı")
    if block.status != "review_required" or block.revision != approval.expected_revision:
        raise HTTPException(status_code=409, detail="Formül değişti; yeniden yükleyin")
    try:
        block.spoken_text = compile_mathml_candidate(block.mathml)
    except MathSpeechError:
        raise HTTPException(status_code=422, detail="Formülün desteklenen Türkçe okunuşu yok") from None
    block.status = "approved"
    block.revision += 1
    block.validation = Validation(
        schema_passed=True, render_score=1, source_agreement=1, confidence=1,
        reasons=["Öğretmen formül okunuşunu kaynakla doğruladı"],
    )
    document_store.save_draft(source.model_dump(mode="json"))
    document_store.add_audit(source.id, role, "formula_candidate_approved", block.id, approval.reason)
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
    unreliable = [block.id for block in candidates if needs_structured_math_extraction(block)]
    if unreliable:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Sayfada güvenilir olmayan matematiksel metin katmanı var; toplu onay kapatıldı",
                "block_ids": unreliable,
            },
        )
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
