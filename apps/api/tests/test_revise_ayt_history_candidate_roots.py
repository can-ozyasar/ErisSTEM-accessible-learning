import hashlib
import json

from app.pipeline.revise_ayt_history_candidate_roots import ROOT_REVISIONS, revise


def _checksum(questions):
    raw = [{key: value for key, value in item.items() if key not in {"status", "runtime_enabled"}} for item in questions]
    return hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_revises_all_source_dependent_roots_and_invalidates_checksum():
    questions = [{"id": identifier, "question": "Kaynağa göre eski kök", "spoken_question": "Kaynağa göre eski sesletim",
                  "status": "source_crop_validation_required", "runtime_enabled": False}
                 for identifier in ROOT_REVISIONS]
    questions.extend({"id": f"other-{index}", "question": "Bağımsız soru", "spoken_question": "Bağımsız soru",
                      "status": "source_crop_validation_required", "runtime_enabled": False}
                     for index in range(120 - len(questions)))
    candidate = {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": _checksum(questions), "questions": questions}

    revised = revise(candidate)

    assert revised["candidate_checksum"] != candidate["candidate_checksum"]
    assert not any(question["question"].startswith("Kaynağa göre") for question in revised["questions"])
    assert revised["root_revision"]["prior_candidate_checksum"] == candidate["candidate_checksum"]
    assert all(question["runtime_enabled"] is False for question in revised["questions"])
