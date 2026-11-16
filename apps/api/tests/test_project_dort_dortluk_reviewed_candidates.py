import hashlib
import json

import pytest

from app.pipeline.project_dort_dortluk_reviewed_candidates import build


def _question(number):
    return {
        "number": number,
        "question_type": "multiple_choice",
        "parts": [{"text": "Mustafa Kemal hangi görevde bulunmuştur?"}],
        "choices": [{"label": label, "text": f"Seçenek {label}"} for label in "ABCDE"],
        "visuals": [],
    }


def _inputs():
    checksum = "source-checksum"
    row = {"candidate_id": "clean", "question": _question(1),
           "answer_key_accessed": False, "worked_explanation_accessed": False,
           "source_checksum": checksum}
    candidates = {
        "schema": "ogm-dort-dortluk-ayt-target-candidates-v1",
        "source_checksum": checksum,
        "scope_manifest_checksum": "scope-manifest-checksum",
        "rows": [row],
        "review_queue": [{"candidate_id": "layout-warning"}],
    }
    review = {
        "schema": "independent-ogm-history-teacher-review-v1",
        "review_metadata": {
            "reviewer_kind": "independent_agent_history_teacher",
            "is_agent_review": True,
            "is_human_teacher_approval": False,
            "source_manifest_sha256": "",
            "candidate_count": 2,
            "reviewed_candidate_count": 2,
            "answer_keys_accessed": False,
            "worked_solutions_accessed": False,
        },
        "summary": {"transcription_counts": {"exact": 2}},
        "reviews": [
            {"candidate_id": "clean", "target_section": "1.3",
             "transcription_match": "exact", "visual_independence": "text_only",
             "coaching_candidate": "candidate"},
            {"candidate_id": "layout-warning", "target_section": "3.1",
             "transcription_match": "exact", "visual_independence": "text_only",
             "coaching_candidate": "candidate"},
        ],
    }
    manifest = {
        "schema": "ogm-dort-dortluk-teacher-review-pack-v1",
        "source_checksum": checksum,
        "candidate_count": 2,
        "rows": [{"candidate_id": "clean"}, {"candidate_id": "layout-warning"}],
    }
    serialized_manifest = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    manifest_checksum = hashlib.sha256(serialized_manifest).hexdigest()
    review["review_metadata"]["source_manifest_sha256"] = manifest_checksum
    return candidates, review, manifest, manifest_checksum


def test_projects_only_clean_text_candidates_and_keeps_agent_review_unapproved():
    result = build(*_inputs())
    assert len(result["rows"]) == 1
    assert result["rows"][0]["candidate_id"] == "clean"
    assert result["rows"][0]["topic"] == "I. Dünya Savaşı Sürecinde Osmanlı Devleti"
    assert result["rows"][0]["answer_key_accessed"] is False
    assert result["scope_review"]["is_human_teacher_approval"] is False
    assert result["runtime_enabled"] is False
    assert result["qlora_enabled"] is False


def test_projection_rejects_a_manifest_mismatch():
    candidates, review, manifest, _ = _inputs()
    review["review_metadata"]["source_manifest_sha256"] = "wrong-manifest"
    with pytest.raises(ValueError, match="provenance"):
        build(candidates, review, manifest, "wrong-manifest")
