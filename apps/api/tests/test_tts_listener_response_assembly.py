import hashlib
import json
from pathlib import Path

import pytest

from app.pipeline.tts_listener_response_assembly import assemble_listener_responses


def fixture_files(tmp_path: Path) -> tuple[list[Path], list[Path], Path]:
    digest = hashlib.sha256(b"audio").hexdigest()
    run = tmp_path / "run.json"
    run.write_text(json.dumps({
        "schema_version": "tts-synthesis-run-v1", "candidate": "voice-a",
        "records": [{"id": "text-01", "kind": "text", "status": "generated", "audio_sha256": digest}],
    }), encoding="utf-8")
    packets, responses = [], []
    for index in range(3):
        reviewer = f"reviewer-{index}"
        packet = tmp_path / f"packet-{index}.json"
        packet.write_text(json.dumps({
            "schema_version": "tts-listener-packet-v1", "study_id": "study-01",
            "reviewer_id": reviewer, "candidate_quality_report_sha256": "a" * 64,
            "items": [{"id": "text-01", "audio_sha256": digest}],
        }), encoding="utf-8")
        response = tmp_path / f"response-{index}.json"
        response.write_text(json.dumps({
            "study_id": "study-01", "reviewer_id": reviewer,
            "responses": [{"id": "text-01", "audio_sha256": digest, "matches_reference": True,
                           "intelligible": True, "serious_artifact": False}],
        }), encoding="utf-8")
        packets.append(packet)
        responses.append(response)
    return packets, responses, run


def test_assembly_binds_three_reviewers_to_exact_audio_and_run(tmp_path: Path):
    packets, responses, run = fixture_files(tmp_path)
    study = assemble_listener_responses(packets, responses, run)
    assert len(study.reviewers) == 3
    assert study.synthesis_run_sha256 == hashlib.sha256(run.read_bytes()).hexdigest()


def test_assembly_rejects_a_tampered_response(tmp_path: Path):
    packets, responses, run = fixture_files(tmp_path)
    payload = json.loads(responses[0].read_text(encoding="utf-8"))
    payload["responses"][0]["audio_sha256"] = "b" * 64
    responses[0].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="listener_response_audio_binding_mismatch"):
        assemble_listener_responses(packets, responses, run)


def test_assembly_requires_three_independent_reviewers(tmp_path: Path):
    packets, responses, run = fixture_files(tmp_path)
    with pytest.raises(ValueError, match="three_matching_reviewers_required"):
        assemble_listener_responses(packets[:2], responses[:2], run)
