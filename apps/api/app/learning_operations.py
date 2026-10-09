"""Version-bound expert and consented pilot evidence; never generated approvals."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import JSON, Integer, String, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from .job_store import Base
from .pipeline.learning_experience import (
    AIRPLANE_TASKS,
    CIRCLE_TASKS,
    SET_BASELINE,
    SET_REVIEW,
    read_module,
)
from .pipeline.set_practice import EXERCISES, expected_answer


class LearningRecord(Base):
    __tablename__ = "learning_records"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    module_id: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExpertChecks(StrictInput):
    concept_correctness: bool
    representation_limits: bool
    answer_keys: bool
    hint_boundaries: bool
    language_clarity: bool


class ExpertReview(StrictInput):
    revision: int = Field(ge=0)
    content_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["approve", "changes_requested"]
    expertise: Literal["special_education", "subject_teacher", "accessibility"]
    evidence_reference: str = Field(min_length=3, max_length=200)
    checks: ExpertChecks
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def complete_approval(self):
        if self.decision == "approve" and not all(self.checks.model_dump().values()):
            raise ValueError("Onay için bütün içerik kontrolleri tamamlanmalı")
        if self.decision == "changes_requested" and not self.note:
            raise ValueError("Düzeltme isteği için açıklama gerekli")
        return self


PILOT_TASKS = (
    {"id": "open-topic", "title": "Atölyeden konuyu açma"},
    {"id": "question-access", "title": "Soruyu ve bütün seçenekleri inceleme"},
    {"id": "description", "title": "Kısa, ayrıntılı ve nesne keşfi açıklamasını ayırma"},
    {"id": "answer-entry", "title": "Yanıt girme ve gönderme"},
    {"id": "feedback", "title": "Geribildirim ve ipucuna erişme"},
    {"id": "navigation", "title": "İlerleme ve geri dönme"},
    {"id": "summary", "title": "İlk yanıt ve yardım sonuçlarını ayırma"},
    {"id": "erase-records", "title": "Cihazdaki atölye kayıtlarını silme"},
)


class PilotCreate(StrictInput):
    module_id: str
    content_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    kind: Literal["rehearsal", "participant"] = "rehearsal"
    adult_consent: bool = False
    consent_reference: str = Field(default="", max_length=200)
    device: Literal["desktop", "android", "ios", "other"]
    access_tool: Literal["nvda", "talkback", "voiceover", "braille", "magnification", "other"]

    @model_validator(mode="after")
    def require_consent(self):
        if self.kind == "participant" and (not self.adult_consent or len(self.consent_reference) < 3):
            raise ValueError("Yetişkin katılımcının rızası ve private rıza kaydı referansı gerekli")
        return self


class Observation(StrictInput):
    result: Literal["independent", "with_help", "not_completed", "skipped"]
    researcher_help_count: int = Field(ge=0, le=100)
    category: Literal["access", "representation", "concept", "input_format", "source_error", "uncertain"] | None = None
    severity: Literal["minor", "major", "blocking"] | None = None
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def consistent_observation(self):
        if self.result == "independent" and self.researcher_help_count:
            raise ValueError("Dış yardım alınan görev bağımsız olarak işaretlenemez")
        if self.result == "with_help" and self.researcher_help_count == 0:
            raise ValueError("Yardımlı görev için yardım sayısı gerekli")
        if (self.category is None) != (self.severity is None):
            raise ValueError("Sorun türü ve önem düzeyi birlikte belirtilmeli")
        return self


class PilotObservation(StrictInput):
    revision: int = Field(ge=1)
    observation: Observation


class RevisionRequest(StrictInput):
    revision: int = Field(ge=0)


def marking_keys(module_id: str) -> dict:
    if module_id == "sets":
        tasks = SET_BASELINE
        keys = {task.id: {"answer": sorted(expected_answer(task)), "hints": list(task.hints)}
                for task in (*EXERCISES, *SET_REVIEW)}
    else:
        tasks = CIRCLE_TASKS if module_id == "circle" else AIRPLANE_TASKS
        keys = {}
    keys.update({task.public.id: {"answer": task.correct_choice, "hint": task.hint} for task in tasks})
    return keys


def content_checksum(module_id: str) -> str:
    module = read_module(module_id)
    if module is None:
        raise HTTPException(404, "Öğrenme içeriği bulunamadı")
    payload = {"module": module.model_dump(), "marking": marking_keys(module_id)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def require_current(module_id: str, checksum: str):
    if checksum != content_checksum(module_id):
        raise HTTPException(409, "İçerik değişmiş. Güncel sürümü yeniden inceleyin.")


def timestamp():
    return datetime.now(UTC).isoformat()


class LearningOperationsStore:
    def __init__(self, sessions):
        self.sessions = sessions

    def get(self, record_id: str):
        with self.sessions() as session:
            record = session.get(LearningRecord, record_id)
            return {**record.payload, "id": record.id, "revision": record.revision} if record else None

    def list(self, kind: str, module_id: str | None = None):
        with self.sessions() as session:
            query = select(LearningRecord).where(LearningRecord.kind == kind)
            if module_id is not None:
                query = query.where(LearningRecord.module_id == module_id)
            return [{**record.payload, "id": record.id, "revision": record.revision}
                    for record in session.scalars(query.order_by(LearningRecord.id))]

    def save(self, record_id: str, kind: str, module_id: str, payload: dict, revision: int):
        payload = {key: value for key, value in payload.items() if key not in {"id", "revision"}}
        with self.sessions() as session:
            try:
                if revision == 0:
                    session.add(LearningRecord(id=record_id, kind=kind, module_id=module_id,
                                               payload=payload, revision=1))
                    session.flush()
                else:
                    changed = session.execute(update(LearningRecord).where(
                        LearningRecord.id == record_id, LearningRecord.revision == revision,
                    ).values(payload=payload, revision=revision + 1))
                    if changed.rowcount != 1:
                        raise HTTPException(409, "Kayıt değişmiş. Güncel kaydı yeniden yükleyin.")
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise HTTPException(409, "Kayıt değişmiş. Güncel kaydı yeniden yükleyin.") from error
        return self.get(record_id)

    def quality(self, module_id: str):
        checksum = content_checksum(module_id)
        review = self.get(f"review:{module_id}")
        pilots = self.list("pilot", module_id)
        approved = bool(review and review.get("decision") == "approve" and
                        review.get("content_checksum") == checksum)
        valid_pilots = [pilot for pilot in pilots if
                        pilot["kind"] == "participant" and pilot["state"] == "completed" and
                        pilot["content_checksum"] == checksum and
                        all(observation["severity"] != "blocking" for observation in pilot["observations"].values()) and
                        all(pilot["observations"].get(task, {}).get("result") == "independent"
                            for task in ("question-access", "answer-entry", "navigation"))]
        blocking_pilots = [pilot for pilot in pilots if pilot["kind"] == "participant" and
                           pilot["content_checksum"] == checksum and
                           any(item["severity"] == "blocking" for item in pilot["observations"].values())]
        published = bool(approved and valid_pilots and not blocking_pilots and review.get("published_at"))
        return {"content_checksum": checksum,
                "status": "published" if published else "expert-approved" if approved else "unreviewed",
                "expert_approved": approved, "qualifying_pilots": len(valid_pilots),
                "pilot_count": len(pilots), "blocking_pilots": len(blocking_pilots),
                "revision": review["revision"] if review else 0,
                "published_at": review.get("published_at") if published else None}

    def expert_review(self, module_id: str, request: ExpertReview, actor_role: str):
        require_current(module_id, request.content_checksum)
        previous = self.get(f"review:{module_id}")
        history = (previous or {}).get("history", [])[-19:]
        event = {**request.model_dump(exclude={"revision"}), "at": timestamp(), "actor_role": actor_role}
        return self.save(f"review:{module_id}", "review", module_id,
                         {**event, "published_at": None, "history": [*history, event]}, request.revision)

    def publish(self, module_id: str, revision: int):
        quality = self.quality(module_id)
        if not quality["expert_approved"] or not quality["qualifying_pilots"] or quality["blocking_pilots"]:
            raise HTTPException(409, "Güncel uzman onayı ve tamamlanmış gerçek kullanıcı pilotu gerekli")
        previous = self.get(f"review:{module_id}")
        return self.save(f"review:{module_id}", "review", module_id,
                         {**previous, "published_at": timestamp()}, revision)

    def create_pilot(self, request: PilotCreate):
        require_current(request.module_id, request.content_checksum)
        module = read_module(request.module_id)
        return self.save(str(uuid4()), "pilot", request.module_id,
                         {**request.model_dump(), "module_version": module.version,
                          "participant_code": f"P-{uuid4().hex[:8]}", "state": "active",
                          "created_at": timestamp(), "observations": {}}, 0)

    def pilot(self, pilot_id: str):
        pilot = self.get(pilot_id)
        if pilot is None or "observations" not in pilot:
            raise HTTPException(404, "Pilot bulunamadı")
        return pilot

    def observe(self, pilot_id: str, task_id: str, request: PilotObservation):
        pilot = self.pilot(pilot_id)
        if pilot["state"] != "active":
            raise HTTPException(409, "Tamamlanmış pilot değiştirilemez; yeni oturum açın")
        if task_id not in {task["id"] for task in PILOT_TASKS}:
            raise HTTPException(404, "Görev bulunamadı")
        require_current(pilot["module_id"], pilot["content_checksum"])
        observations = {**pilot["observations"], task_id: request.observation.model_dump()}
        return self.save(pilot_id, "pilot", pilot["module_id"],
                         {**pilot, "observations": observations}, request.revision)

    def complete(self, pilot_id: str, revision: int):
        pilot = self.pilot(pilot_id)
        require_current(pilot["module_id"], pilot["content_checksum"])
        if pilot["state"] != "active" or set(pilot["observations"]) != {task["id"] for task in PILOT_TASKS}:
            raise HTTPException(409, "Her görev için bir gözlem kaydı gerekli")
        return self.save(pilot_id, "pilot", pilot["module_id"],
                         {**pilot, "state": "completed", "completed_at": timestamp()}, revision)

    def delete_pilot(self, pilot_id: str, revision: int):
        pilot = self.pilot(pilot_id)
        with self.sessions() as session:
            removed = session.execute(delete(LearningRecord).where(
                LearningRecord.id == pilot_id, LearningRecord.revision == revision))
            if removed.rowcount != 1:
                raise HTTPException(409, "Kayıt değişmiş. Güncel kaydı yeniden yükleyin.")
            review = session.get(LearningRecord, f"review:{pilot['module_id']}")
            if review is not None:
                changed = session.execute(update(LearningRecord).where(
                    LearningRecord.id == review.id, LearningRecord.revision == review.revision,
                ).values(payload={**review.payload, "published_at": None, "pilot_withdrawn_at": timestamp()},
                         revision=review.revision + 1))
                if changed.rowcount != 1:
                    raise HTTPException(409, "Yayın kaydı değişmiş. Kaydı yeniden yükleyin.")
            session.commit()
