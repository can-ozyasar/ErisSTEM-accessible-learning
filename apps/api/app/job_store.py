"""İş kuyruğu kalıcılığı: PostgreSQL üretim, SQLite geliştirme/test uyumluluğu."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    inspect,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .migrations import apply_postgres_migrations


class Base(DeclarativeBase):
    pass


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        UniqueConstraint(
            "source_checksum",
            "pipeline_version",
            "selected_pages",
            name="uq_job_source_pipeline_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source_relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    selected_pages: Mapped[str] = mapped_column(String(1000), nullable=False, default="all")
    pipeline_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=JobStatus.QUEUED)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class ContentDocument(Base):
    __tablename__ = "content_documents"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    draft_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    published_payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class DocumentAudit(Base):
    __tablename__ = "document_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(100), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    block_id: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(String(500), nullable=False)


class BenchmarkAnnotation(Base):
    __tablename__ = "benchmark_annotations"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    expected: Mapped[str] = mapped_column(String(10000), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TableReview(Base):
    """Private, source-bound table review state; student content is separate."""

    __tablename__ = "table_reviews"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(100), nullable=False)
    candidate_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    draft_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    published_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    return f"sqlite:///{Path.cwd() / 'eristem-dev.db'}"


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    engine = create_engine(url or database_url(), pool_pre_ping=True)
    apply_postgres_migrations(engine)
    Base.metadata.create_all(engine)
    # Sadece yerel geliştirme DB'si için geriye dönük küçük şema yükseltmesi.
    # Üretim PostgreSQL'i apps/api/migrations/ ile yükseltilir.
    if engine.dialect.name == "sqlite":
        columns = {column["name"] for column in inspect(engine).get_columns("processing_jobs")}
        if "source_relative_path" not in columns:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE processing_jobs ADD COLUMN source_relative_path VARCHAR(512)"
                )
        if "selected_pages" not in columns:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE processing_jobs ADD COLUMN selected_pages VARCHAR(1000) DEFAULT 'all'"
                )
        table_review_columns = {
            column["name"] for column in inspect(engine).get_columns("table_reviews")
        } if "table_reviews" in inspect(engine).get_table_names() else set()
        if table_review_columns and "candidate_payload" not in table_review_columns:
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE table_reviews ADD COLUMN candidate_payload JSON")
                connection.exec_driver_sql(
                    "UPDATE table_reviews SET candidate_payload = draft_payload WHERE candidate_payload IS NULL"
                )
    return sessionmaker(engine, expire_on_commit=False)


def normalize_selected_pages(selected_pages: str | None) -> str:
    """Sayfa seçimini deterministik iş idempotency anahtarına dönüştürür."""
    if selected_pages is None or selected_pages.strip().lower() == "all":
        return "all"
    try:
        pages = sorted({int(value.strip()) for value in selected_pages.split(",")})
    except ValueError as exc:
        raise ValueError("Seçili sayfalar virgülle ayrılmış pozitif tam sayılar olmalı") from exc
    if not pages or pages[0] < 1:
        raise ValueError("Seçili sayfalar pozitif tam sayılar olmalı")
    return ",".join(map(str, pages))


class JobStore:
    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def enqueue(
        self,
        source_checksum: str,
        source_relative_path: str,
        pipeline_version: str,
        selected_pages: str | None = None,
    ) -> tuple[ProcessingJob, bool]:
        """Aynı kaynak+sürüm+sayfa kapsamı için mevcut işi döndürür."""
        selected_pages = normalize_selected_pages(selected_pages)
        with self.sessions() as session:
            existing = session.scalar(
                select(ProcessingJob).where(
                    ProcessingJob.source_checksum == source_checksum,
                    ProcessingJob.pipeline_version == pipeline_version,
                    ProcessingJob.selected_pages == selected_pages,
                )
            )
            if existing is not None:
                return existing, False
            now = datetime.now(UTC)
            job = ProcessingJob(
                id=str(uuid4()),
                source_checksum=source_checksum,
                source_relative_path=source_relative_path,
                selected_pages=selected_pages,
                pipeline_version=pipeline_version,
                status=JobStatus.QUEUED,
                attempts=0,
                created_at=now,
                updated_at=now,
            )
            session.add(job)
            try:
                session.commit()
                return job, True
            except IntegrityError:
                # Ayrı bir worker aynı idempotency anahtarını aynı anda eklemiş olabilir.
                session.rollback()
                existing = session.scalar(
                    select(ProcessingJob).where(
                        ProcessingJob.source_checksum == source_checksum,
                        ProcessingJob.pipeline_version == pipeline_version,
                        ProcessingJob.selected_pages == selected_pages,
                    )
                )
                if existing is None:  # Beklenmeyen bir bütünlük hatasını gizleme.
                    raise
                return existing, False

    def list_recent(self) -> list[ProcessingJob]:
        with self.sessions() as session:
            return list(
                session.scalars(select(ProcessingJob).order_by(ProcessingJob.created_at.desc()))
            )

    def claim_next(self) -> ProcessingJob | None:
        """Bir worker'ın işlemesi için sıradaki işi sahiplenir."""
        with self.sessions.begin() as session:
            job = session.scalar(
                select(ProcessingJob)
                .where(ProcessingJob.status == JobStatus.QUEUED)
                .order_by(ProcessingJob.created_at)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            job.status = JobStatus.RUNNING
            job.attempts += 1
            job.updated_at = datetime.now(UTC)
            return job

    def finish(self, job_id: str) -> None:
        self._set_terminal_status(job_id, JobStatus.SUCCEEDED, None)

    def fail(self, job_id: str, error_code: str) -> None:
        self._set_terminal_status(job_id, JobStatus.FAILED, error_code)

    def _set_terminal_status(self, job_id: str, status: JobStatus, error_code: str | None) -> None:
        with self.sessions.begin() as session:
            job = session.get(ProcessingJob, job_id)
            if job is None:
                raise LookupError("İş bulunamadı")
            if job.status != JobStatus.RUNNING:
                raise RuntimeError("İş running durumda değil")
            job.status = status
            job.last_error_code = error_code
            job.updated_at = datetime.now(UTC)


class DocumentStore:
    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def ensure(self, payload: dict) -> None:
        with self.sessions.begin() as session:
            if session.get(ContentDocument, payload["id"]):
                return
            published = {
                **payload,
                "blocks": [b for b in payload["blocks"] if b["status"] == "published"],
            }
            session.add(
                ContentDocument(
                    id=payload["id"], draft_payload=payload, published_payload=published
                )
            )

    def create_draft(self, payload: dict) -> None:
        """Worker çıktısını yalnız taslak olarak saklar; yayımlanmış içerik boş başlar."""
        with self.sessions.begin() as session:
            record = session.get(ContentDocument, payload["id"])
            if record is None:
                empty_published = {**payload, "blocks": []}
                session.add(
                    ContentDocument(
                        id=payload["id"], draft_payload=payload, published_payload=empty_published
                    )
                )
            else:
                record.draft_payload = payload

    def reset_for_test(self, payload: dict) -> None:
        with self.sessions.begin() as session:
            session.query(DocumentAudit).delete()
            session.query(ContentDocument).delete()
        self.ensure(payload)

    def get(self, document_id: str, published: bool = False) -> dict | None:
        with self.sessions() as session:
            record = session.get(ContentDocument, document_id)
            return (
                None
                if record is None
                else (record.published_payload if published else record.draft_payload)
            )

    def list_drafts(self) -> list[dict]:
        with self.sessions() as session:
            return list(
                session.scalars(select(ContentDocument.draft_payload).order_by(ContentDocument.id))
            )

    def list_published(self) -> list[dict]:
        with self.sessions() as session:
            return [
                payload for payload in session.scalars(
                    select(ContentDocument.published_payload).order_by(ContentDocument.id)
                ) if payload and payload.get("blocks")
            ]

    def save_draft(self, payload: dict) -> None:
        with self.sessions.begin() as session:
            record = session.get(ContentDocument, payload["id"])
            if record is None:
                raise LookupError("Belge bulunamadı")
            record.draft_payload = payload

    def publish(self, payload: dict) -> None:
        with self.sessions.begin() as session:
            record = session.get(ContentDocument, payload["id"])
            if record is None:
                raise LookupError("Belge bulunamadı")
            record.draft_payload = payload
            record.published_payload = payload

    def add_audit(
        self, document_id: str, actor_role: str, action: str, block_id: str | None, detail: str
    ) -> None:
        with self.sessions.begin() as session:
            session.add(
                DocumentAudit(
                    id=str(uuid4()),
                    document_id=document_id,
                    at=datetime.now(UTC),
                    actor_role=actor_role,
                    action=action,
                    block_id=block_id,
                    detail=detail,
                )
            )

    def audit(self) -> list[DocumentAudit]:
        with self.sessions() as session:
            return list(session.scalars(select(DocumentAudit).order_by(DocumentAudit.at)))


class TableReviewStore:
    """Store only reviewable vector/native tables, never raw model artefacts."""

    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def create(self, payload: dict) -> TableReview:
        with self.sessions.begin() as session:
            if session.get(TableReview, payload["id"]):
                raise ValueError("Tablo denetim kaydı zaten var")
            now = datetime.now(UTC)
            record = TableReview(
                id=payload["id"], document_id=payload["document_id"], candidate_payload=payload, draft_payload=payload,
                published_payload=None, status="review_required", revision=1,
                created_at=now, updated_at=now,
            )
            session.add(record)
            return record

    def reset_for_test(self) -> None:
        with self.sessions.begin() as session:
            session.query(TableReview).delete()

    def get(self, table_id: str) -> TableReview | None:
        with self.sessions() as session:
            return session.get(TableReview, table_id)

    def list_pending(self) -> list[TableReview]:
        with self.sessions() as session:
            return list(session.scalars(select(TableReview).where(TableReview.status == "review_required").order_by(TableReview.created_at)))

    def list_teacher_approved(self) -> list[TableReview]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(TableReview)
                    .where(TableReview.status.in_(("approved", "published")))
                    .order_by(TableReview.created_at)
                )
            )

    def list_published_for_document(self, document_id: str) -> list[TableReview]:
        with self.sessions() as session:
            return list(session.scalars(
                select(TableReview)
                .where(TableReview.document_id == document_id, TableReview.status == "published")
                .order_by(TableReview.created_at, TableReview.id)
            ))

    def save(self, table_id: str, payload: dict, *, status: str, revision: int) -> TableReview:
        with self.sessions.begin() as session:
            record = session.get(TableReview, table_id)
            if record is None:
                raise LookupError("Tablo denetim kaydı bulunamadı")
            record.draft_payload, record.status, record.revision = payload, status, revision
            record.updated_at = datetime.now(UTC)
            return record

    def publish(self, table_id: str) -> TableReview:
        with self.sessions.begin() as session:
            record = session.get(TableReview, table_id)
            if record is None:
                raise LookupError("Tablo denetim kaydı bulunamadı")
            record.status = "published"
            record.published_payload = record.draft_payload
            record.updated_at = datetime.now(UTC)
            return record
