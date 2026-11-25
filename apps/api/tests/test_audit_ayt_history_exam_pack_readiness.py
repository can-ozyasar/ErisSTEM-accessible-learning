import json

import pytest

from app.pipeline.audit_ayt_history_exam_pack_readiness import audit


def _question(index: int) -> dict:
    return {
        "id": f"question-{index:03d}", "authorship": "original", "status": "approved",
        "runtime_enabled": False, "human_pdf_crop_review": True,
        "review_artifact_checksum": "a" * 64,
        "source_evidence": [{"source_id": "meb-history", "source_checksum": "b" * 64,
                             "page": 1, "bbox": [1, 2, 3, 4]}],
    }


def _write_inputs(tmp_path, reviewed=True):
    questions = [_question(index) for index in range(120)]
    if not reviewed:
        questions[0].pop("human_pdf_crop_review")
        questions[0].pop("review_artifact_checksum")
    splits = (["development"] * 72 + ["retrieval_test"] * 24 + ["system_acceptance"] * 24)
    candidate = tmp_path / "candidate.json"
    split = tmp_path / "split.json"
    candidate.write_text(json.dumps({"schema": "ayt-history-original-question-candidate-pack-v1",
                                     "candidate_checksum": "c" * 64, "corpus_checksum": "d" * 64,
                                     "questions": questions}), encoding="utf-8")
    split.write_text(json.dumps({"schema": "ayt-history-candidate-split-v1",
                                 "records": [{"id": question["id"], "split": name}
                                             for question, name in zip(questions, splits)]}), encoding="utf-8")
    return candidate, split


def test_audit_blocks_ai_only_candidate_without_human_pdf_review(tmp_path):
    candidate, split = _write_inputs(tmp_path, reviewed=False)
    result = audit(candidate, split)
    assert result["runtime_pack_may_be_built"] is False
    assert result["eligible_question_count"] == 119
    assert result["blocker_counts"] == {
        "human_pdf_crop_review_missing": 1, "human_review_artifact_missing": 1,
    }
    assert result["answer_key_accessed"] is False


def test_audit_accepts_complete_human_reviewed_pack(tmp_path):
    candidate, split = _write_inputs(tmp_path)
    result = audit(candidate, split)
    assert result["runtime_pack_may_be_built"] is True
    assert result["split_counts"] == {"development": 72, "retrieval_test": 24, "system_acceptance": 24}


def test_audit_rejects_non_frozen_split(tmp_path):
    candidate, split = _write_inputs(tmp_path)
    content = json.loads(split.read_text())
    content["records"][0]["split"] = "other"
    split.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(ValueError, match="72/24/24"):
        audit(candidate, split)
