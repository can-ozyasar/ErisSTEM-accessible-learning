import hashlib

import pytest

from app.pipeline.tts_listener_study import (
    TtsListenerStudy,
    TtsSynthesisRun,
    build_listener_packets,
    evaluate_listener_study,
)
from app.pipeline.tts_quality import TtsGoldManifest

QUALITY_SHA = "a" * 64
RUN_SHA = "b" * 64


def gold() -> TtsGoldManifest:
    return TtsGoldManifest.model_validate(
        {
            "schema_version": "tts-gold-v1",
            "items": [
                {
                    "id": f"item-{index:02d}",
                    "kind": "formula" if index % 2 else "table",
                    "expected_spoken_text": f"private reference {index}",
                    "critical_tokens": ["private"],
                }
                for index in range(1, 51)
            ],
        }
    )


def synthesis_run() -> TtsSynthesisRun:
    return TtsSynthesisRun.model_validate(
        {
            "schema_version": "tts-synthesis-run-v1",
            "candidate": "voice-a",
            "records": [
                {
                    "id": f"item-{index:02d}",
                    "kind": "formula" if index % 2 else "table",
                    "status": "generated",
                    "audio_sha256": hashlib.sha256(f"audio-{index}".encode()).hexdigest(),
                }
                for index in range(1, 51)
            ],
        }
    )


def automatic_quality_report() -> dict[str, object]:
    return {
        "report_type": "tts-quality-evaluation-v1",
        "candidate": "voice-a",
        "decision": "tts-candidate-passed-listener-study-required",
    }


def study(*, serious_artifact: bool = False) -> TtsListenerStudy:
    run = synthesis_run()
    audio = {record.id: record.audio_sha256 for record in run.records}
    return TtsListenerStudy.model_validate(
        {
            "schema_version": "tts-listener-study-v1",
            "study_id": "study-001",
            "candidate_quality_report_sha256": QUALITY_SHA,
            "synthesis_run_sha256": RUN_SHA,
            "reviewers": [
                {
                    "reviewer_id": f"reviewer-{reviewer}",
                    "responses": [
                        {
                            "id": item_id,
                            "audio_sha256": audio[item_id],
                            "matches_reference": True,
                            "intelligible": True,
                            "serious_artifact": serious_artifact and reviewer == 1 and item_id == "item-01",
                        }
                        for item_id in sorted(audio)
                    ],
                }
                for reviewer in range(1, 4)
            ],
        }
    )


def test_listener_packets_are_blind_to_candidate_identity_but_bind_the_passed_quality_report():
    packets = build_listener_packets(
        gold(),
        synthesis_run(),
        automatic_quality_report(),
        QUALITY_SHA,
        study_id="study-001",
        reviewer_ids=["reviewer-1", "reviewer-2", "reviewer-3"],
    )

    assert len(packets) == 3
    assert all(packet["blind_candidate_label"] == "candidate-a" for packet in packets)
    assert all(packet["candidate_quality_report_sha256"] == QUALITY_SHA for packet in packets)
    assert all(len(packet["items"]) == 50 for packet in packets)
    assert "voice-a" not in str(packets)


def test_listener_study_passes_only_after_three_complete_matching_reviews():
    report = evaluate_listener_study(
        gold(), synthesis_run(), automatic_quality_report(), QUALITY_SHA, RUN_SHA, study()
    )

    assert report["decision"] == "tts-listener-study-passed"
    assert report["contains_document_content"] is False
    assert report["contains_listener_identity"] is False
    assert len(report["records"]) == 50
    assert "private reference" not in str(report)


def test_listener_study_blocks_a_single_serious_audio_artifact():
    report = evaluate_listener_study(
        gold(), synthesis_run(), automatic_quality_report(), QUALITY_SHA, RUN_SHA, study(serious_artifact=True)
    )

    assert report["decision"] == "tts-listener-study-blocked"
    assert report["records"][0]["serious_artifact_count"] == 1


def test_listener_study_rejects_results_bound_to_a_different_synthesis_run():
    with pytest.raises(ValueError, match="synthesis_run_checksum_mismatch"):
        evaluate_listener_study(
            gold(), synthesis_run(), automatic_quality_report(), QUALITY_SHA, "c" * 64, study()
        )


def test_listener_packet_refuses_to_start_before_automatic_quality_passes():
    failed = automatic_quality_report() | {"decision": "tts-candidate-blocked"}

    with pytest.raises(ValueError, match="requires_passed_automatic"):
        build_listener_packets(
            gold(), synthesis_run(), failed, QUALITY_SHA, study_id="study-001", reviewer_ids=["reviewer-1"]
        )
