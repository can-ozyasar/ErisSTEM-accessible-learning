"""Integrity gate for reviewed TTS audio assets served to students.

Audio is never inferred from a filename alone. Every asset is bound to the
published document revision and the hash of its already-verified spoken unit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .accessibility_reader import ReadingUnit

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class TtsAudioAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    filename: str = Field(min_length=5, max_length=255)
    spoken_text_sha256: str = Field(pattern=SHA256_PATTERN)
    audio_sha256: str = Field(pattern=SHA256_PATTERN)
    bytes: int = Field(gt=0)

    @model_validator(mode="after")
    def safe_wav_filename(self) -> TtsAudioAsset:
        path = Path(self.filename)
        if path.name != self.filename or path.suffix.lower() != ".wav":
            raise ValueError("unsafe_or_unsupported_audio_filename")
        return self


class TtsAudioAssetManifest(BaseModel):
    """Private manifest approved only after automatic and listener evaluation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    document_id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    published_revision: int = Field(ge=1)
    candidate: str = Field(min_length=1, max_length=100)
    voice_profile: str = Field(min_length=1, max_length=100)
    candidate_quality_report_sha256: str = Field(pattern=SHA256_PATTERN)
    listener_study_report_sha256: str = Field(pattern=SHA256_PATTERN)
    listener_study_passed: bool
    assets: list[TtsAudioAsset] = Field(min_length=1)

    @model_validator(mode="after")
    def final_quality_gate_and_unique_assets(self) -> TtsAudioAssetManifest:
        if self.schema_version != "verified-tts-audio-assets-v2":
            raise ValueError("invalid_tts_audio_asset_schema")
        if not self.listener_study_passed:
            raise ValueError("listener_study_required_before_student_audio")
        unit_ids = [asset.unit_id for asset in self.assets]
        filenames = [asset.filename for asset in self.assets]
        if len(unit_ids) != len(set(unit_ids)) or len(filenames) != len(set(filenames)):
            raise ValueError("tts_audio_assets_must_be_unique")
        return self


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_audio_manifest(path: Path) -> TtsAudioAssetManifest:
    try:
        return TtsAudioAssetManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("invalid_or_missing_tts_audio_asset_manifest") from error


def _require_release_evidence(manifest: TtsAudioAssetManifest, root: Path, unit: ReadingUnit) -> None:
    """Do not trust a manifest's self-declared listener flag without evidence."""
    reports = []
    for filename, expected_sha in (
        ("quality_report.json", manifest.candidate_quality_report_sha256),
        ("listener_report.json", manifest.listener_study_report_sha256),
    ):
        path = (root / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha256_file(path) != expected_sha:
            raise ValueError("tts_release_evidence_integrity_mismatch")
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("invalid_tts_release_evidence") from error
        if not isinstance(report, dict):
            raise ValueError("invalid_tts_release_evidence")
        reports.append(report)
    quality, listener = reports
    kind = "text" if unit.kind in {"heading", "paragraph"} else unit.kind
    eligible = quality.get("eligible_kinds")
    kind_results = quality.get("kind_results")
    kind_result = kind_results.get(kind) if isinstance(kind_results, dict) else None
    if (
        quality.get("report_type") != "tts-quality-evaluation-v1"
        or quality.get("contains_document_content") is not False
        or quality.get("quality_policy_version") != "tts-quality-policy-v3"
        or quality.get("evaluation_scope") != "source-bound-release"
        or quality.get("candidate") != manifest.candidate
        or quality.get("decision") not in {
            "tts-candidate-passed-listener-study-required",
            "tts-candidate-kind-limited-listener-study-required",
        }
        or not isinstance(eligible, list)
        or kind not in eligible
        or not isinstance(quality.get("gold_samples"), int)
        or quality["gold_samples"] < 50
        or not isinstance(kind_result, dict)
        or not isinstance(kind_result.get("gold_samples"), int)
        or kind_result["gold_samples"] < 10
        or kind_result.get("automatic_screen") != "passed"
    ):
        raise ValueError("tts_quality_release_evidence_not_eligible")
    records = listener.get("records")
    kind_records = [record for record in records if isinstance(record, dict) and record.get("kind") == kind] if isinstance(records, list) else []
    if (
        listener.get("report_type") != "tts-listener-study-evaluation-v1"
        or listener.get("decision") != "tts-listener-study-passed"
        or listener.get("candidate") != manifest.candidate
        or listener.get("candidate_quality_report_sha256") != manifest.candidate_quality_report_sha256
        or not isinstance(listener.get("reviewers"), int)
        or listener["reviewers"] < 3
        or listener.get("malformed_reviewer_count") != 0
        or not isinstance(records, list)
        or len(kind_records) < 10
        or not all(
            isinstance(record, dict)
            and isinstance(record.get("valid_reviews"), int)
            and record["valid_reviews"] >= 3
            and record.get("all_match_reference") is True
            and record.get("all_intelligible") is True
            and record.get("serious_artifact_count") == 0
            for record in kind_records
        )
    ):
        raise ValueError("tts_listener_release_evidence_not_passed")


def resolve_verified_audio(
    manifest: TtsAudioAssetManifest,
    audio_root: Path,
    *,
    document_id: str,
    published_revision: int,
    unit: ReadingUnit,
) -> tuple[Path, TtsAudioAsset]:
    """Return a WAV only when all release and integrity bindings match."""
    if manifest.document_id != document_id or manifest.published_revision != published_revision:
        raise ValueError("audio_manifest_document_revision_mismatch")
    asset = next((item for item in manifest.assets if item.unit_id == unit.id), None)
    if asset is None or asset.spoken_text_sha256 != sha256_text(unit.spoken_text):
        raise ValueError("audio_manifest_unit_mismatch")
    root = audio_root.resolve()
    _require_release_evidence(manifest, root, unit)
    path = (root / asset.filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("audio_asset_missing_or_outside_root")
    if path.stat().st_size != asset.bytes or sha256_file(path) != asset.audio_sha256:
        raise ValueError("audio_asset_integrity_mismatch")
    return path, asset
