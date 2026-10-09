import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import learning_operations as operations
from app.exam_practice import PROFILES, TASKS, ExamCreate, ExamStore
from app.job_store import make_session_factory
from app.learning_operations import (
    PILOT_TASKS,
    ExpertReview,
    LearningOperationsStore,
    Observation,
    PilotCreate,
    PilotObservation,
    content_checksum,
)
from app.learning_routes import learning_router


@pytest.fixture
def setup(tmp_path):
    sessions = make_session_factory(f"sqlite:///{tmp_path / 'learning.db'}")
    store = LearningOperationsStore(sessions)
    exams = ExamStore(store)
    app = FastAPI()
    app.include_router(learning_router(store, exams))
    return store, exams, TestClient(app)


def review_request(revision=0):
    return ExpertReview(
        revision=revision, content_checksum=content_checksum("circle"), decision="approve",
        expertise="special_education", evidence_reference="test-only-evidence",
        checks={key: True for key in ("concept_correctness", "representation_limits", "answer_keys",
                                     "hint_boundaries", "language_clarity")},
    )


def pilot(store, kind="rehearsal", blocking=False):
    created = store.create_pilot(PilotCreate(
        module_id="circle", content_checksum=content_checksum("circle"), kind=kind,
        adult_consent=kind == "participant", consent_reference="test-only-consent",
        device="desktop", access_tool="nvda",
    ))
    for task in PILOT_TASKS:
        observation = Observation(result="independent", researcher_help_count=0,
                                  category="access" if blocking else None,
                                  severity="blocking" if blocking else None)
        created = store.observe(created["id"], task["id"], PilotObservation(
            revision=created["revision"], observation=observation))
    return store.complete(created["id"], created["revision"])


def test_staff_endpoints_reject_students_and_publish_has_separate_role(setup):
    _, _, client = setup
    assert client.get("/v1/teacher/learning/modules").status_code == 401
    assert client.get("/v1/teacher/learning/modules", headers={"X-Role": "student"}).status_code == 403
    assert client.get("/v1/teacher/learning/pilots", headers={"X-Role": "student"}).status_code == 403
    assert client.post("/v1/reviewer/learning/modules/circle/publish",
                       headers={"X-Role": "teacher"}, json={"revision": 0}).status_code == 403
    assert client.post("/v1/teacher/learning/modules/circle/review", headers={"X-Role": "reviewer"},
                       json=review_request().model_dump()).status_code == 403


def test_publication_requires_current_expert_and_real_pilot_and_survives_restart(setup):
    store, _, _ = setup
    with pytest.raises(HTTPException):
        store.publish("circle", 0)
    review = store.expert_review("circle", review_request(), "teacher")
    pilot(store)  # Researcher rehearsal is explicitly not real user evidence.
    assert store.quality("circle")["qualifying_pilots"] == 0
    with pytest.raises(HTTPException):
        store.publish("circle", review["revision"])
    participant = pilot(store, "participant")
    store.publish("circle", review["revision"])
    assert LearningOperationsStore(store.sessions).quality("circle")["status"] == "published"
    store.delete_pilot(participant["id"], participant["revision"])
    assert store.quality("circle")["status"] != "published"
    assert store.get(participant["id"]) is None


def test_a_new_critical_report_blocks_existing_release(setup):
    store, _, _ = setup
    review = store.expert_review("circle", review_request(), "teacher")
    pilot(store, "participant")
    store.publish("circle", review["revision"])
    pilot(store, "participant", blocking=True)
    assert store.quality("circle")["blocking_pilots"] == 1
    assert store.quality("circle")["status"] != "published"
    with pytest.raises(HTTPException):
        store.publish("circle", store.quality("circle")["revision"])


def test_marking_changes_invalidate_old_expert_and_pilot_evidence(setup, monkeypatch):
    store, _, _ = setup
    review = store.expert_review("circle", review_request(), "teacher")
    participant = pilot(store, "participant")
    store.publish("circle", review["revision"])
    old = operations.marking_keys
    monkeypatch.setattr(operations, "marking_keys", lambda module: {**old(module), "changed": "test"})
    assert store.quality("circle")["expert_approved"] is False
    assert store.quality("circle")["qualifying_pilots"] == 0
    with pytest.raises(HTTPException):
        store.expert_review("circle", review_request().model_copy(update={"content_checksum": participant["content_checksum"]}), "teacher")


def test_consent_incomplete_checks_and_stale_edits_are_rejected(setup):
    store, _, client = setup
    headers = {"X-Role": "teacher"}
    request = review_request().model_dump()
    request["checks"]["answer_keys"] = False
    assert client.post("/v1/teacher/learning/modules/circle/review", headers=headers, json=request).status_code == 422
    request = {"module_id": "circle", "content_checksum": content_checksum("circle"),
               "kind": "participant", "adult_consent": False, "device": "desktop", "access_tool": "nvda"}
    assert client.post("/v1/teacher/learning/pilots", headers=headers, json=request).status_code == 422
    store.expert_review("circle", review_request(), "teacher")
    with pytest.raises(HTTPException) as conflict:
        store.expert_review("circle", review_request(), "teacher")
    assert conflict.value.status_code == 409
    created = store.create_pilot(PilotCreate(module_id="circle", content_checksum=content_checksum("circle"),
                                           device="desktop", access_tool="nvda"))
    with pytest.raises(HTTPException):
        store.complete(created["id"], created["revision"])


def test_release_enforcement_covers_legacy_and_new_student_endpoints(setup, monkeypatch):
    from app import main
    store, _, _ = setup
    monkeypatch.setattr(main, "learning_operations_store", store)
    monkeypatch.setenv("LEARNING_REQUIRE_RELEASE", "true")
    client = TestClient(main.app)
    headers = {"X-Role": "student"}
    assert client.get("/v1/student/learning/modules", headers=headers).json() == []
    assert client.get("/v1/student/learning/modules/circle", headers=headers).status_code == 409
    assert client.get("/v1/student/practice/sets", headers=headers).status_code == 409
    assert client.post("/v1/student/practice/sets/union-guided/check", headers=headers,
                       json={"answer": "{1,2,3,4}", "attempt": 1}).status_code == 409


def test_sourced_profiles_do_not_share_extra_time_rules():
    profiles = {item.id: item for item in PROFILES}
    assert profiles["lgs-reader-2026"].slots[1].base_minutes == 80
    assert [slot.extra_minutes for slot in profiles["yks-reader-2026"].slots] == [30, 50, 60]
    assert profiles["ekpss-reader-2026"].slots[0].extra_minutes == 40
    assert profiles["ekpss-self-read-2026"].slots[0].extra_minutes == 0
    assert all(profile.year == 2026 and profile.verified_at == "2026-10-09" for profile in PROFILES)


def test_exam_hides_solutions_until_finish_preserves_revision_and_erases_raw_answers(setup):
    store, _, client = setup
    headers = {"X-Role": "student"}
    started = client.post("/v1/student/exams/sessions", headers=headers, json={
        "profile_id": "yks-reader-2026", "slot_id": "tyt", "arrangement_confirmed": True,
        "mode": "full"}).json()
    assert started["duration_minutes"] == 195
    assert started["results"] is None
    assert "correct" not in json_text(started["questions"])
    assert "explanation" not in json_text(started["questions"])
    answer = {"revision": started["revision"], "question_id": "e1", "answer": "option-1", "flagged": True}
    saved = client.put(f"/v1/student/exams/sessions/{started['id']}/answer", headers=headers, json=answer).json()
    assert saved["results"] is None and saved["flags"]["e1"] is True
    assert client.put(f"/v1/student/exams/sessions/{started['id']}/answer", headers=headers, json=answer).status_code == 409
    assert ExamStore(LearningOperationsStore(store.sessions)).get(saved["id"])["answers"]["e1"] == "option-1"
    finished = client.post(f"/v1/student/exams/sessions/{saved['id']}/finish", headers=headers,
                           json={"revision": saved["revision"]}).json()
    assert finished["results"][0]["correct"] is True
    assert finished["answers"] == {} and store.get(saved["id"])["answers"] == {}
    assert client.put(f"/v1/student/exams/sessions/{saved['id']}/answer", headers=headers,
                      json={**answer, "revision": finished["revision"]}).status_code == 409
    assert client.delete(f"/v1/student/exams/sessions/{saved['id']}?revision={finished['revision']}", headers=headers).status_code == 204
    assert store.get(saved["id"]) is None


def json_text(data):
    import json
    return json.dumps(data)


def test_exam_deadline_is_server_enforced_and_expired_replay_cannot_change_score(setup, monkeypatch):
    _, exams, client = setup
    clock = [1000.0]
    monkeypatch.setattr(exams, "now", lambda: clock[0])
    exam = exams.create(ExamCreate(profile_id="lgs-reader-2026", slot_id="numeric",
                                  arrangement_confirmed=True, short_minutes=1))
    clock[0] = exam["deadline"]
    assert exams.get(exam["id"])["state"] == "finished"
    response = client.put(f"/v1/student/exams/sessions/{exam['id']}/answer", headers={"X-Role": "student"},
                          json={"revision": exam["revision"], "question_id": "e1", "answer": "option-1"})
    assert response.status_code == 409
    assert not any(item["correct"] for item in exams.get(exam["id"])["results"])


def test_exam_creation_requires_confirmation_and_profile_slot_match(setup):
    _, _, client = setup
    headers = {"X-Role": "student"}
    assert client.get("/v1/student/exams/profiles").status_code == 401
    payload = {"profile_id": "lgs-reader-2026", "slot_id": "tyt", "arrangement_confirmed": True}
    assert client.post("/v1/student/exams/sessions", headers=headers, json=payload).status_code == 422
    payload["slot_id"] = "numeric"
    payload["arrangement_confirmed"] = False
    assert client.post("/v1/student/exams/sessions", headers=headers, json=payload).status_code == 422
    assert len(TASKS) == 6


def test_maintenance_erases_abandoned_raw_answers_and_deletes_old_sessions(setup, monkeypatch):
    store, exams, _ = setup
    clock = [1000.0]
    monkeypatch.setattr(exams, "now", lambda: clock[0])
    exam = exams.create(ExamCreate(profile_id="lgs-reader-2026", slot_id="numeric",
                                  arrangement_confirmed=True, short_minutes=1))
    from app.exam_practice import ExamAnswer
    saved = exams.answer(exam["id"], ExamAnswer(revision=exam["revision"], question_id="e1", answer="option-1"))
    clock[0] = saved["deadline"] + 1
    assert exams.cleanup()["expired"] == 1
    assert store.get(exam["id"])["answers"] == {}
    clock[0] = 1000 + 7 * 86400
    assert exams.cleanup()["removed"] == 1
    assert store.get(exam["id"]) is None
