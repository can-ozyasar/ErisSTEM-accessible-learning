import pytest

from app.pipeline.ogm_ayt_target_section_proposals import propose


def _row(stem, topic="Millî Mücadele"):
    return {
        "candidate_id": stem,
        "topic": topic,
        "question": {"stem": stem, "choices": []},
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
    }


def test_proposes_section_without_approving():
    result = propose({
        "schema": "ogm-ayt-private-transcription-v1",
        "source_checksum": "x",
        "rows": [_row("Havza ve Amasya genelgeleri")],
    })
    item = result["proposals"][0]
    assert item["candidate_section_ids"] == ["2.1"]
    assert item["status"] == "proposal_only"
    assert item["needs_pdf_crop_review"] is True
    assert result["runtime_enabled"] is False


def test_ambiguous_broad_topic_stays_broad():
    result = propose({
        "schema": "ogm-ayt-private-transcription-v1",
        "source_checksum": "x",
        "rows": [_row("Millî Mücadele gelişmeleri")],
    })
    item = result["proposals"][0]
    assert item["confidence"] == "ambiguous"
    assert set(item["candidate_section_ids"]) == {"2.1", "2.4", "2.5"}


def test_answer_bearing_rows_rejected():
    row = _row("Havza")
    row["answer_key_accessed"] = True
    with pytest.raises(ValueError):
        propose({"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "x", "rows": [row]})
