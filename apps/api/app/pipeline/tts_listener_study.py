"""Private, blind listener-study gate for a Turkish STEM TTS candidate.

Automatic transcription is a useful screening mechanism, but cannot certify
whether a learner can understand a voice.  This module therefore binds a
blind listener review to both the exact synthesis run and the already-passed
automatic quality report.  It never writes reference text, listener identity,
or WAV paths into its resulting aggregate report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .tts_audio_assets import SHA256_PATTERN, sha256_file
from .tts_quality import TtsGoldManifest

VALID_KINDS = {"text", "formula", "table", "chart", "exercise"}
MIN_BLIND_REVIEWERS = 3
MIN_REVIEWS_PER_SAMPLE = 3


class TtsSynthesisRecord(BaseModel):
    """A generated WAV binding from the private synthesis-run report."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    kind: str
    status: str
    audio_sha256: str = Field(pattern=SHA256_PATTERN)
    duration_seconds: float | None = Field(default=None, gt=0)
    generation_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def generated_kind_is_known(self) -> TtsSynthesisRecord:
        if self.kind not in VALID_KINDS or self.status != "generated":
            raise ValueError("listener_study_requires_generated_known_kind_audio")
        return self


class TtsSynthesisRun(BaseModel):
    """The minimal, content-free portion of a private synthesis run."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str
    candidate: str = Field(min_length=1, max_length=100)
    records: list[TtsSynthesisRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def exact_unique_audio_records(self) -> TtsSynthesisRun:
        if self.schema_version != "tts-synthesis-run-v1":
            raise ValueError("invalid_tts_synthesis_run_schema")
        ids = [record.id for record in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_tts_synthesis_record_ids")
        return self


class ListenerResponse(BaseModel):
    """One blind assessment; the reference sentence stays in the private packet."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    audio_sha256: str = Field(pattern=SHA256_PATTERN)
    matches_reference: bool
    intelligible: bool
    serious_artifact: bool


class ListenerReviewer(BaseModel):
    """Pseudonymous reviewer records, never emitted by the aggregate report."""

    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    responses: list[ListenerResponse] = Field(min_length=1)

    @model_validator(mode="after")
    def response_ids_are_unique(self) -> ListenerReviewer:
        ids = [response.id for response in self.responses]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_listener_response_ids")
        return self


class TtsListenerStudy(BaseModel):
    """Private blind-review results bound to a candidate run and quality report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    study_id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    candidate_quality_report_sha256: str = Field(pattern=SHA256_PATTERN)
    synthesis_run_sha256: str = Field(pattern=SHA256_PATTERN)
    reviewers: list[ListenerReviewer] = Field(min_length=1)

    @model_validator(mode="after")
    def reviewer_ids_are_unique(self) -> TtsListenerStudy:
        if self.schema_version != "tts-listener-study-v1":
            raise ValueError("invalid_tts_listener_study_schema")
        ids = [reviewer.reviewer_id for reviewer in self.reviewers]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_listener_reviewer_ids")
        return self


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _expected_audio(gold: TtsGoldManifest, run: TtsSynthesisRun) -> dict[str, TtsSynthesisRecord]:
    if gold.schema_version != "tts-gold-v1":
        raise ValueError("invalid_tts_gold_schema")
    expected = {item.id: item for item in gold.items}
    actual = {record.id: record for record in run.records}
    if set(actual) != set(expected):
        raise ValueError("listener_study_synthesis_ids_do_not_match_gold")
    for item_id, item in expected.items():
        if actual[item_id].kind != item.kind:
            raise ValueError("listener_study_synthesis_kind_mismatch")
    return actual


def _require_automatic_quality_report(
    report: dict[str, object],
    *,
    candidate: str,
    expected_sha256: str,
) -> set[str]:
    """Return the content kinds that may enter the listener study.

    A policy-v2 quality report can pass one safe content class while keeping
    the other classes blocked.  Requiring an explicit, non-empty allow-list
    prevents a partially qualified voice from being reviewed or packaged for
    a different kind by accident.
    """
    eligible = report.get("eligible_kinds")
    if (
        report.get("report_type") != "tts-quality-evaluation-v1"
        or report.get("candidate") != candidate
        or report.get("decision")
        not in {
            "tts-candidate-passed-listener-study-required",
            "tts-candidate-kind-limited-listener-study-required",
        }
        or not isinstance(eligible, list)
        or not eligible
        or not all(isinstance(kind, str) and kind in VALID_KINDS for kind in eligible)
        or not isinstance(expected_sha256, str)
        or not re_fullmatch_sha256(expected_sha256)
    ):
        raise ValueError("listener_study_requires_passed_automatic_tts_quality")
    return set(eligible)


def build_listener_packets(
    gold: TtsGoldManifest,
    run: TtsSynthesisRun,
    automatic_quality_report: dict[str, object],
    automatic_quality_report_sha256: str,
    *,
    study_id: str,
    reviewer_ids: list[str],
) -> list[dict[str, object]]:
    """Create blinded private review packets after the automatic gate passed.

    Packets include the exact reference sentence because a listener must judge
    it against audio, but omit the model/candidate identity.  They are private
    inputs, never student API artefacts.
    """
    if not re_fullmatch_identifier(study_id) or len(set(reviewer_ids)) != len(reviewer_ids) or not reviewer_ids:
        raise ValueError("invalid_listener_packet_identifiers")
    if not all(re_fullmatch_identifier(reviewer_id) for reviewer_id in reviewer_ids):
        raise ValueError("invalid_listener_packet_identifiers")
    audio = _expected_audio(gold, run)
    eligible_kinds = _require_automatic_quality_report(
        automatic_quality_report,
        candidate=run.candidate,
        expected_sha256=automatic_quality_report_sha256,
    )
    packets = []
    for reviewer_id in reviewer_ids:
        items = [
            {
                "id": item.id,
                "kind": item.kind,
                "audio_sha256": audio[item.id].audio_sha256,
                "reference_spoken_text": item.expected_spoken_text,
            }
            for item in gold.items
            if item.kind in eligible_kinds
        ]
        items.sort(key=lambda item: _sha256_text(f"{study_id}:{reviewer_id}:{item['id']}"))
        packets.append(
            {
                "schema_version": "tts-listener-packet-v1",
                "study_id": study_id,
                "reviewer_id": reviewer_id,
                "blind_candidate_label": "candidate-a",
                "candidate_quality_report_sha256": automatic_quality_report_sha256,
                "items": items,
            }
        )
    return packets


def re_fullmatch_identifier(value: str) -> bool:
    """Keep packet identifiers aligned with Pydantic's public ID contract."""
    import re

    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", value))


def re_fullmatch_sha256(value: str) -> bool:
    import re

    return bool(re.fullmatch(SHA256_PATTERN, value))


def evaluate_listener_study(
    gold: TtsGoldManifest,
    run: TtsSynthesisRun,
    automatic_quality_report: dict[str, object],
    automatic_quality_report_sha256: str,
    synthesis_run_sha256: str,
    study: TtsListenerStudy,
) -> dict[str, object]:
    """Fail closed unless independent reviewers accept every exact WAV sample."""
    audio = _expected_audio(gold, run)
    eligible_kinds = _require_automatic_quality_report(
        automatic_quality_report,
        candidate=run.candidate,
        expected_sha256=automatic_quality_report_sha256,
    )
    if study.candidate_quality_report_sha256 != automatic_quality_report_sha256:
        raise ValueError("listener_study_quality_report_checksum_mismatch")
    if study.synthesis_run_sha256 != synthesis_run_sha256:
        raise ValueError("listener_study_synthesis_run_checksum_mismatch")

    eligible_items = [item for item in gold.items if item.kind in eligible_kinds]
    expected_ids = {item.id for item in eligible_items}
    reviews_by_id: dict[str, list[ListenerResponse]] = {item_id: [] for item_id in expected_ids}
    malformed_reviewer_count = 0
    for reviewer in study.reviewers:
        responses = {response.id: response for response in reviewer.responses}
        if set(responses) != expected_ids:
            malformed_reviewer_count += 1
            continue
        for item_id, response in responses.items():
            if response.audio_sha256 != audio[item_id].audio_sha256:
                malformed_reviewer_count += 1
                break
        else:
            for item_id, response in responses.items():
                reviews_by_id[item_id].append(response)

    records = []
    for item in eligible_items:
        reviews = reviews_by_id[item.id]
        records.append(
            {
                "id": item.id,
                "kind": item.kind,
                "valid_reviews": len(reviews),
                "all_match_reference": bool(reviews) and all(review.matches_reference for review in reviews),
                "all_intelligible": bool(reviews) and all(review.intelligible for review in reviews),
                "serious_artifact_count": sum(review.serious_artifact for review in reviews),
            }
        )
    complete = (
        len(study.reviewers) >= MIN_BLIND_REVIEWERS
        and malformed_reviewer_count == 0
        and all(record["valid_reviews"] >= MIN_REVIEWS_PER_SAMPLE for record in records)
    )
    passed = complete and all(
        record["all_match_reference"]
        and record["all_intelligible"]
        and record["serious_artifact_count"] == 0
        for record in records
    )
    return {
        "report_type": "tts-listener-study-evaluation-v1",
        "contains_document_content": False,
        "contains_listener_identity": False,
        "candidate": run.candidate,
        "candidate_quality_report_sha256": automatic_quality_report_sha256,
        "synthesis_run_sha256": synthesis_run_sha256,
        "reviewers": len(study.reviewers),
        "minimum_blind_reviewers": MIN_BLIND_REVIEWERS,
        "minimum_reviews_per_sample": MIN_REVIEWS_PER_SAMPLE,
        "malformed_reviewer_count": malformed_reviewer_count,
        "decision": "tts-listener-study-passed" if passed else "tts-listener-study-blocked",
        "records": records,
    }


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("invalid_or_missing_private_json") from error
    if not isinstance(payload, dict):
        raise TypeError("private_json_root_must_be_object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a private blind Turkish STEM TTS listener study")
    commands = parser.add_subparsers(dest="command", required=True)
    packets = commands.add_parser("build-packets", help="Create private blind listener packets after automatic approval")
    packets.add_argument("--gold", type=Path, required=True)
    packets.add_argument("--synthesis-run", type=Path, required=True)
    packets.add_argument("--automatic-quality-report", type=Path, required=True)
    packets.add_argument("--study-id", required=True)
    packets.add_argument("--reviewer-id", action="append", required=True)
    packets.add_argument("--output-dir", type=Path, required=True)
    evaluate = commands.add_parser("evaluate", help="Aggregate private blind listener responses")
    evaluate.add_argument("--gold", type=Path, required=True)
    evaluate.add_argument("--synthesis-run", type=Path, required=True)
    evaluate.add_argument("--automatic-quality-report", type=Path, required=True)
    evaluate.add_argument("--study", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    gold = TtsGoldManifest.model_validate(_load_json(args.gold))
    run = TtsSynthesisRun.model_validate(_load_json(args.synthesis_run))
    report = _load_json(args.automatic_quality_report)
    quality_report_sha256 = sha256_file(args.automatic_quality_report)
    if args.command == "build-packets":
        if args.output_dir.exists():
            raise FileExistsError("refusing_to_overwrite_listener_packets")
        packets = build_listener_packets(
            gold,
            run,
            report,
            quality_report_sha256,
            study_id=args.study_id,
            reviewer_ids=args.reviewer_id,
        )
        args.output_dir.mkdir(parents=True)
        for packet in packets:
            destination = args.output_dir / f"{packet['reviewer_id']}.json"
            destination.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"schema_version": "tts-listener-packet-v1", "packets": len(packets)}, ensure_ascii=False))
        return 0
    if args.output.exists():
        raise FileExistsError("refusing_to_overwrite_listener_study_report")
    study = TtsListenerStudy.model_validate(_load_json(args.study))
    evaluation = evaluate_listener_study(
        gold,
        run,
        report,
        quality_report_sha256,
        sha256_file(args.synthesis_run),
        study,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: evaluation[key] for key in ("report_type", "reviewers", "decision")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
