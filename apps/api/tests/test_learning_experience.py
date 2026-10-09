import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.learning_experience import (
    AIRPLANE_TASKS,
    CIRCLE_TASKS,
    SET_BASELINE,
    SET_REVIEW,
    check_module_answer,
    read_module,
)
from app.pipeline.set_practice import (
    EXERCISES,
    AnswerSubmission,
    check_answer,
    expected_answer,
)

client = TestClient(app)
HEADERS = {"X-Role": "student"}
ROOT = "/v1/student/learning/modules"


def submit(module_id, task_id, answer, attempt=1):
    return client.post(f"{ROOT}/{module_id}/exercises/{task_id}/check", headers=HEADERS,
                       json={"answer": answer, "attempt": attempt})


def test_catalog_requires_role_and_unknown_modules_do_not_fall_back():
    assert client.get(ROOT).status_code == 401
    assert client.get(f"{ROOT}/circle").status_code == 401
    assert client.post(f"{ROOT}/circle/exercises/circle-baseline/check",
                       json={"answer": "option-1", "attempt": 1}).status_code == 401
    assert {item["id"] for item in client.get(ROOT, headers=HEADERS).json()} == {
        "sets", "circle", "airplane",
    }
    assert client.get(f"{ROOT}/unknown", headers=HEADERS).status_code == 404
    assert submit("circle", "airplane-baseline", "option-1").status_code == 404
    assert submit("unknown", "circle-baseline", "option-1").status_code == 404


def test_catalog_describes_usage_and_representations_without_requiring_school_year_or_diagnosis():
    catalog = client.get(ROOT, headers=HEADERS).json()
    contexts = {context for item in catalog for context in item["scope"]["applicable_contexts"]}
    assert {"formal_learning", "exam_preparation", "higher_education", "daily_or_professional"} <= contexts
    for item in catalog:
        scope = item["scope"]
        assert scope["applicable_contexts"] and scope["representation_options"]
        assert scope["context_note"]
        assert "school_year" not in item and "diagnosis" not in item


@pytest.mark.parametrize("module_id", ["sets", "circle", "airplane"])
def test_public_contract_separates_lessons_and_phases_and_never_ships_marking_keys(module_id):
    response = client.get(f"{ROOT}/{module_id}", headers=HEADERS)
    assert response.status_code == 200
    public = response.json()
    assert "Uzman ve kullanıcı değerlendirmesi bekliyor" in public["provenance"]
    assert public["scope"]["applicable_contexts"]
    stages = [item["stage"] for item in public["exercises"]]
    order = {"baseline": 0, "guided": 1, "transfer": 2, "review": 3}
    assert stages == sorted(stages, key=order.get)
    assert set(stages) == set(order)
    assert len({item["id"] for item in public["exercises"]}) == len(stages)
    assert public["review_delay_hours"] == 24
    lesson_ids = {item["id"] for item in public["lessons"]}
    for task in public["exercises"]:
        assert task["lesson_id"] in lesson_ids
        assert "correct_choice" not in task and "expected_answer" not in task and "hint" not in task
        assert "hints" not in task
        if task["answer_kind"] == "choice":
            assert len(task["choices"]) >= 2
            assert len({item["id"] for item in task["choices"]}) == len(task["choices"])


@pytest.mark.parametrize("module_id,tasks", [
    ("sets", SET_BASELINE), ("circle", CIRCLE_TASKS), ("airplane", AIRPLANE_TASKS),
])
def test_all_choice_answers_and_hint_boundaries(module_id, tasks):
    for task in tasks:
        assert submit(module_id, task.public.id, task.correct_choice).json()["correct"]
        for option in task.public.choices:
            if option.id == task.correct_choice:
                continue
            response = submit(module_id, task.public.id, option.id).json()
            assert not response["correct"] and response["valid"]
            assert response["error_kind"] == "answer_mismatch"
            assert bool(response["hint"]) == (task.public.stage == "guided")
        invalid = submit(module_id, task.public.id, "invented-option").json()
        assert not invalid["valid"] and invalid["error_kind"] == "format"


def test_set_review_uses_fresh_values_and_never_gives_hints():
    assert not ({task.left for task in EXERCISES} & {task.left for task in SET_REVIEW})
    for task in (*EXERCISES, *SET_REVIEW):
        answer = "{" + ",".join(map(str, sorted(expected_answer(task)))) + "}"
        assert submit("sets", task.id, answer).json()["correct"]
    for task in SET_REVIEW:
        result = submit("sets", task.id, "{99}", attempt=99).json()
        assert result["hint"] is None
    assert submit("sets", "union-guided", "1+2").json()["error_kind"] == "format"


def test_relationship_specific_hints_are_not_psychological_diagnoses_or_solutions():
    cases = [
        ("union-guided", "{2}", "ortak"),
        ("intersection-guided", "{1,2,3,4}", "bütün"),
        ("difference-guided", "{3}", "sırasını"),
        ("union-guided", "{99}", "kaynağını"),
    ]
    tasks = {task.id: task for task in EXERCISES}
    for task_id, answer, word in cases:
        result = check_answer(tasks[task_id], AnswerSubmission(answer=answer, attempt=1))
        assert word in result.hint
        assert "{" not in result.hint
        assert "kendiniz" not in result.message


def test_bad_requests_and_marking_do_not_mutate_public_content():
    before = read_module("circle").model_dump()
    assert submit("circle", "circle-baseline", "option-1", attempt=0).status_code == 422
    assert submit("sets", "union-guided", "x" * 101).status_code == 422
    check_module_answer("circle", "circle-baseline", AnswerSubmission(answer="option-1", attempt=1))
    assert read_module("circle").model_dump() == before
