"""İş kuyruğu kalıcılığı: PostgreSQL üretim, SQLite geliştirme/test uyumluluğu."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, create_engine, select
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
    return sessionmaker(engine, expire_on_commit=False)


class JobStore:
    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def enqueue(self, source_checksum: str, pipeline_version: str) -> tuple[ProcessingJob, bool]:
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
