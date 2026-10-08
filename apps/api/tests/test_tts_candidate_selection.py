import json
from pathlib import Path

from app.pipeline.tts_candidate_selection import _read_quality_report, select_tts_candidates


def quality(candidate: str, eligible_kinds: list[str]) -> dict:
    return {
        "report_type": "tts-quality-evaluation-v1",
        "contains_document_content": False,
        "candidate": candidate,
        "decision": "tts-candidate-blocked" if not eligible_kinds else "tts-candidate-kind-limited-listener-study-required",
        "eligible_kinds": eligible_kinds,
        "kind_results": {},
        "pronunciation_accuracy": 0.9,
        "critical_token_accuracy": 0.7,
    }


def test_selection_fails_closed_when_every_candidate_is_blocked(tmp_path: Path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps(quality("voice-a", [])), encoding="utf-8")
    second.write_text(json.dumps(quality("voice-b", [])), encoding="utf-8")

    report = select_tts_candidates([(first, _read_quality_report(first)), (second, _read_quality_report(second))])

    assert report["selection"] == "no_candidate_eligible"
    assert report["eligible_candidate_count"] == 0
    assert report["contains_document_content"] is False


def test_selection_allows_listener_study_only_for_explicitly_eligible_kinds(tmp_path: Path):
    report_path = tmp_path / "candidate.json"
    report_path.write_text(json.dumps(quality("voice-a", ["text"])), encoding="utf-8")

    report = select_tts_candidates([(report_path, _read_quality_report(report_path))])

    assert report["selection"] == "listener_study_required_before_any_audio_asset"
    assert report["candidates"][0]["eligible_kinds"] == ["text"]
