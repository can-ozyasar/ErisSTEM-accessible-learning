"""İş kuyruğu kalıcılığı: PostgreSQL üretim, SQLite geliştirme/test uyumluluğu."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (UniqueConstraint("source_checksum", "pipeline_version", name="uq_job_source_pipeline"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source_relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=JobStatus.QUEUED)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    return f"sqlite:///{Path.cwd() / 'eristem-dev.db'}"


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    engine = create_engine(url or database_url(), pool_pre_ping=True)
    Base.metadata.create_all(engine)
    # Sadece yerel geliştirme DB'si için geriye dönük küçük şema yükseltmesi.
    # Üretim PostgreSQL'i apps/api/migrations/0002_processing_job_source_path.sql ile yükseltilir.
    if engine.dialect.name == "sqlite":
        columns = {column["name"] for column in inspect(engine).get_columns("processing_jobs")}
        if "source_relative_path" not in columns:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE processing_jobs ADD COLUMN source_relative_path VARCHAR(512)"
                )
    return sessionmaker(engine, expire_on_commit=False)


class JobStore:
    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def enqueue(
        self, source_checksum: str, source_relative_path: str, pipeline_version: str
    ) -> tuple[ProcessingJob, bool]:
        """Aynı kaynak+sürüm için mevcut işi döndürür; yeni işi yalnız bir kez oluşturur."""
        with self.sessions() as session:
            existing = session.scalar(
                select(ProcessingJob).where(
                    ProcessingJob.source_checksum == source_checksum,
                    ProcessingJob.pipeline_version == pipeline_version,
                )
            )
            if existing is not None:
                return existing, False
            now = datetime.now(UTC)
            job = ProcessingJob(
                id=str(uuid4()),
                source_checksum=source_checksum,
                source_relative_path=source_relative_path,
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
                    )
                )
                if existing is None:  # Beklenmeyen bir bütünlük hatasını gizleme.
                    raise
                return existing, False

    def list_recent(self) -> list[ProcessingJob]:
        with self.sessions() as session:
            return list(session.scalars(select(ProcessingJob).order_by(ProcessingJob.created_at.desc())))

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
