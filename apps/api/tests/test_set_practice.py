from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.set_practice import BY_ID, AnswerSubmission, check_answer, parse_answer

client = TestClient(app)
HEADERS = {"X-Role": "student"}


def test_bank_is_authored_and_does_not_ship_answers_or_hints():
    response = client.get("/v1/student/practice/sets", headers=HEADERS)
    assert response.status_code == 200
    bank = response.json()
    assert len(bank["exercises"]) == 6
    assert "sentetik" in bank["provenance"]
    assert [item["stage"] for item in bank["exercises"]] == ["guided", "transfer"] * 3
    assert all("expected_answer" not in item and "hints" not in item for item in bank["exercises"])


def test_set_answer_is_order_independent_and_rejects_duplicate_or_malformed_input():
    assert parse_answer("{4, 2, 1}") == frozenset({1, 2, 4})
    assert parse_answer("∅") == frozenset()
    for answer in ("1;2", "{1,1}", "1 + 2", "{1001}"):
        response = check_answer(BY_ID["union-guided"], AnswerSubmission(answer=answer, attempt=1))
        assert not response.valid and not response.correct


def test_guided_hints_do_not_return_solution_and_transfer_has_no_hints():
    for attempt in (1, 2, 3, 4):
        guided = client.post("/v1/student/practice/sets/union-guided/check", headers=HEADERS,
                             json={"answer": "{9}", "attempt": attempt})
        assert guided.status_code == 200
        assert guided.json()["hint"]
        assert "{1, 2, 3, 4}" not in str(guided.json())
    transfer = client.post("/v1/student/practice/sets/union-transfer/check", headers=HEADERS,
                           json={"answer": "{9}", "attempt": 2})
    assert transfer.json()["hint"] is None
    assert transfer.json()["correct"] is False


def test_all_operations_and_unknown_exercise():
    answers = {"union-guided": "{4, 3, 2, 1}", "intersection-guided": "{2, 4}",
               "difference-guided": "{1, 4}", "union-transfer": "{0,2,5,6}",
               "intersection-transfer": "{2,5}", "difference-transfer": "{0,5}"}
    for exercise_id, answer in answers.items():
        response = client.post(f"/v1/student/practice/sets/{exercise_id}/check", headers=HEADERS,
                               json={"answer": answer, "attempt": 1})
        assert response.status_code == 200 and response.json()["correct"] is True
    assert client.post("/v1/student/practice/sets/missing/check", headers=HEADERS,
                       json={"answer": "{}", "attempt": 1}).status_code == 404
    assert client.get("/v1/student/practice/sets").status_code == 401
