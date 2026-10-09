from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from .auth import Role, require_roles
from .exam_practice import PROFILES, ExamAnswer, ExamCreate, ExamStore
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

    @router.post("/v1/student/exams/sessions", status_code=201)
    def start_exam(request: ExamCreate, _: Role = student):
        return exams.create(request)

    @router.get("/v1/student/exams/sessions/{exam_id}")
    def read_exam(exam_id: str, _: Role = student):
        return exams.public(exams.get(exam_id))

    @router.put("/v1/student/exams/sessions/{exam_id}/answer")
    def answer(exam_id: str, request: ExamAnswer, _: Role = student):
        return exams.answer(exam_id, request)

    @router.post("/v1/student/exams/sessions/{exam_id}/finish")
    def finish(exam_id: str, request: RevisionRequest, _: Role = student):
        return exams.finish(exam_id, request.revision)

    @router.delete("/v1/student/exams/sessions/{exam_id}", status_code=204)
    def delete_exam(exam_id: str, revision: int, _: Role = student):
        exams.remove(exam_id, revision)
        return Response(status_code=204)

    return router
