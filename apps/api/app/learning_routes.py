from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response

from .auth import Role, require_roles
from .exam_practice import PROFILES, ExamAnswer, ExamCoachTurn, ExamCreate, ExamStore
from .learning_operations import (
    PILOT_TASKS,
    ExpertReview,
    LearningOperationsStore,
    PilotCreate,
    PilotObservation,
    RevisionRequest,
    marking_keys,
)
from .pipeline.learning_experience import module_catalog, read_module
from .local_tts import LocalTtsUnavailable, synthesize_history_text
from .demo_audio import resolve_demo_audio
from .deepseek_exam_coach import is_configured as external_coach_configured
from .pipeline.prepare_ayt_history_v5_audio_manifest import _normalized, _question_ordinal


def learning_router(store: LearningOperationsStore, exams: ExamStore):
    router = APIRouter()
    staff = Depends(require_roles(Role.TEACHER, Role.REVIEWER, Role.ADMIN))
    teacher = Depends(require_roles(Role.TEACHER, Role.ADMIN))
    reviewer = Depends(require_roles(Role.REVIEWER, Role.ADMIN))
    student = Depends(require_roles(Role.STUDENT, Role.TEACHER, Role.REVIEWER, Role.ADMIN))

    @router.get("/v1/teacher/learning/modules")
    def review_catalog(_: Role = staff):
        return [{**module.model_dump(), "quality": store.quality(module.id),
                 "review": store.get(f"review:{module.id}"),
                 "content": read_module(module.id), "marking_keys": marking_keys(module.id)}
                for module in module_catalog()]

    @router.post("/v1/teacher/learning/modules/{module_id}/review")
    def review(module_id: str, request: ExpertReview, role: Role = teacher):
        return store.expert_review(module_id, request, role.value)

    @router.post("/v1/reviewer/learning/modules/{module_id}/publish")
    def publish(module_id: str, request: RevisionRequest, _: Role = reviewer):
        store.publish(module_id, request.revision)
        return store.quality(module_id)

    @router.get("/v1/teacher/learning/pilot-tasks")
    def pilot_tasks(_: Role = staff):
        return list(PILOT_TASKS)

    @router.get("/v1/teacher/learning/pilots")
    def list_pilots(_: Role = staff):
        return store.list("pilot")

    @router.post("/v1/teacher/learning/pilots", status_code=201)
    def create_pilot(request: PilotCreate, _: Role = teacher):
        return store.create_pilot(request)

    @router.get("/v1/teacher/learning/pilots/{pilot_id}")
    def get_pilot(pilot_id: str, _: Role = staff):
        return store.pilot(pilot_id)

    @router.put("/v1/teacher/learning/pilots/{pilot_id}/tasks/{task_id}")
    def observe(pilot_id: str, task_id: str, request: PilotObservation, _: Role = teacher):
        return store.observe(pilot_id, task_id, request)

    @router.post("/v1/teacher/learning/pilots/{pilot_id}/complete")
    def complete(pilot_id: str, request: RevisionRequest, _: Role = teacher):
        return store.complete(pilot_id, request.revision)

    @router.delete("/v1/teacher/learning/pilots/{pilot_id}", status_code=204)
    def delete_pilot(pilot_id: str, revision: int, _: Role = teacher):
        store.delete_pilot(pilot_id, revision)
        return Response(status_code=204)

    @router.get("/v1/student/exams/profiles")
    def profiles(_: Role = student):
        exams.cleanup()
        return list(PROFILES)

    @router.get("/v1/student/exams/coach-capabilities")
    def coach_capabilities(_: Role = student):
        return {"external_coach_configured": external_coach_configured()}

    @router.post("/v1/student/exams/sessions", status_code=201)
    def start_exam(request: ExamCreate, _: Role = student):
        return exams.create(request)

    @router.get("/v1/student/exams/sessions/{exam_id}")
    def read_exam(exam_id: str, _: Role = student):
        return exams.public(exams.get(exam_id))

    @router.get("/v1/student/exams/sessions/{exam_id}/questions/{question_id}/audio/{unit}")
    def exam_question_audio(exam_id: str, question_id: str, unit: str, _: Role = student):
        exams.get(exam_id)  # Reject stale or nonexistent sessions before resolving content.
        tasks = exams.tasks()
        match = next(((index, item) for index, item in enumerate(tasks) if item["id"] == question_id), None)
        if match is None:
            raise HTTPException(404, "Soru bulunamadı")
        position, task = match
        if unit == "stem":
            text = f"{_question_ordinal(position + 1)} soru. {task.get('spoken_question', task['question'])}"
        elif unit in {f"choice-{letter}" for letter in "ABCDE"}:
            index = "ABCDE".index(unit[-1])
            if index >= len(task["choices"]):
                raise HTTPException(404, "Ses birimi bulunamadı")
            text = f"{unit[-1]} şıkkı. {task['choices'][index]}"
        else:
            raise HTTPException(404, "Ses birimi bulunamadı")
        text = _normalized(text)
        source = os.getenv("AYT_HISTORY_EXAM_PACK", "").strip()
        audio_id = f"{question_id}:{unit.lower()}"
        prerecorded = resolve_demo_audio("question", audio_id, text, Path(source)) if source else None
        if prerecorded is not None:
            return Response(content=prerecorded, media_type="audio/wav", headers={"Cache-Control": "no-store", "X-Audio-Source": "fine-tuned-v5"})
        try:
            audio = synthesize_history_text(text)
        except LocalTtsUnavailable as error:
            raise HTTPException(503, "Yerel Türkçe ses hizmeti kullanılamıyor") from error
        return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store", "X-Audio-Source": "piper"})

    @router.put("/v1/student/exams/sessions/{exam_id}/answer")
    def answer(exam_id: str, request: ExamAnswer, _: Role = student):
        return exams.answer(exam_id, request)

    @router.post("/v1/student/exams/sessions/{exam_id}/finish")
    def finish(exam_id: str, request: RevisionRequest, _: Role = student):
        return exams.finish(exam_id, request.revision)

    @router.post("/v1/student/exams/sessions/{exam_id}/review/{question_id}/coach")
    def coach(exam_id: str, question_id: str, request: ExamCoachTurn, _: Role = student):
        return exams.coach(exam_id, question_id, request)

    @router.delete("/v1/student/exams/sessions/{exam_id}", status_code=204)
    def delete_exam(exam_id: str, revision: int, _: Role = student):
        exams.remove(exam_id, revision)
        return Response(status_code=204)

    return router
