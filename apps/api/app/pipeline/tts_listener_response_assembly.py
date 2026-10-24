"""Assemble independently downloaded private listener responses for evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .tts_audio_assets import sha256_file
from .tts_listener_study import ListenerReviewer, TtsListenerStudy, TtsSynthesisRun


def _read(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("invalid_listener_response_input")
    return payload


def assemble_listener_responses(
    packets: list[Path], responses: list[Path], synthesis_run: Path
) -> TtsListenerStudy:
    if len(packets) != len(responses) or len(packets) < 3:
        raise ValueError("three_matching_reviewers_required")
    run = TtsSynthesisRun.model_validate(_read(synthesis_run))
    run_assets = {item.id: item.audio_sha256 for item in run.records}
    study_ids: set[str] = set()
    quality_hashes: set[str] = set()
    reviewers: list[ListenerReviewer] = []
    for packet_path, response_path in zip(packets, responses, strict=True):
        packet, response = _read(packet_path), _read(response_path)
        if packet.get("schema_version") != "tts-listener-packet-v1":
            raise ValueError("invalid_listener_packet_schema")
        if response.get("study_id") != packet.get("study_id") or response.get("reviewer_id") != packet.get("reviewer_id"):
            raise ValueError("listener_response_packet_identity_mismatch")
        items = packet.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("invalid_listener_packet_items")
        expected = {item["id"]: item["audio_sha256"] for item in items}
        if len(expected) != len(items) or any(run_assets.get(item_id) != digest for item_id, digest in expected.items()):
            raise ValueError("listener_packet_audio_binding_mismatch")
        reviewer = ListenerReviewer.model_validate({
            "reviewer_id": response["reviewer_id"], "responses": response.get("responses")
        })
        observed = {item.id: item.audio_sha256 for item in reviewer.responses}
        if observed != expected:
            raise ValueError("listener_response_audio_binding_mismatch")
        study_ids.add(packet["study_id"])
        quality_hashes.add(packet["candidate_quality_report_sha256"])
        reviewers.append(reviewer)
    if len(study_ids) != 1 or len(quality_hashes) != 1:
        raise ValueError("mixed_listener_studies_or_quality_reports")
    return TtsListenerStudy.model_validate({
        "schema_version": "tts-listener-study-v1",
        "study_id": next(iter(study_ids)),
        "candidate_quality_report_sha256": next(iter(quality_hashes)),
        "synthesis_run_sha256": sha256_file(synthesis_run),
        "reviewers": [item.model_dump() for item in reviewers],
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble private blind TTS responses without publishing audio")
    parser.add_argument("--packet", type=Path, action="append", required=True)
    parser.add_argument("--response", type=Path, action="append", required=True)
    parser.add_argument("--synthesis-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing_to_overwrite_listener_study")
    study = assemble_listener_responses(args.packet, args.response, args.synthesis_run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(study.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps({"schema_version": study.schema_version, "reviewers": len(study.reviewers)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
