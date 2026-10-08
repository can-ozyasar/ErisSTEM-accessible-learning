"""Fail-closed provenance registry for external TTS data sources.

An entry records whether a source may enter a particular stage.  It does not
download a dataset, copy audio, or declare that a model has permission simply
because a dataset card exists.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


class TtsSourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    dataset_handle: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    snapshot_revision: str = Field(min_length=7, max_length=128)
    role: Literal["single-speaker-voice-training", "math-text-analysis", "evaluation-only"]
    source_url: AnyHttpUrl
    speaker_reference: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{3,80}$")
    single_speaker_attested: bool = False
    audio_rights_attested: bool = False
    transcript_rights_attested: bool = False
    voice_model_training_permission_attested: bool = False
    withdrawal_process_attested: bool = False
    permission_record_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{3,128}$")

    @model_validator(mode="after")
    def role_shape_is_unambiguous(self) -> TtsSourceRecord:
        if self.role == "single-speaker-voice-training" and not self.speaker_reference:
            raise ValueError("single_speaker_source_requires_speaker_reference")
        if self.role != "single-speaker-voice-training" and self.voice_model_training_permission_attested:
            raise ValueError("voice_training_permission_only_applies_to_voice_training_source")
        return self


class TtsSourceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tts-training-source-registry-v1"]
    sources: list[TtsSourceRecord] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_source_ids(self) -> TtsSourceRegistry:
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_ids_must_be_unique")
        return self


def _voice_training_missing(source: TtsSourceRecord) -> list[str]:
    requirements = {
        "single-speaker-attestation": source.single_speaker_attested,
        "audio-rights-attestation": source.audio_rights_attested,
        "transcript-rights-attestation": source.transcript_rights_attested,
        "voice-model-training-permission": source.voice_model_training_permission_attested,
        "withdrawal-process": source.withdrawal_process_attested,
        "permission-record": bool(source.permission_record_id),
    }
    return [name for name, met in requirements.items() if not met]


def validate_tts_source_registry(registry: TtsSourceRegistry) -> dict:
    """Return a content-free stage eligibility report for source records."""
    records = []
    roles: Counter[str] = Counter()
    for source in registry.sources:
        roles[source.role] += 1
        if source.role == "single-speaker-voice-training":
            missing = _voice_training_missing(source)
            records.append({
                "source_id": source.source_id,
                "role": source.role,
                "decision": "eligible-for-private-corpus-intake" if not missing else "blocked-missing-provenance-or-permission",
                "missing_safeguards": missing,
            })
        else:
            records.append({
                "source_id": source.source_id,
                "role": source.role,
                "decision": "eligible-for-text-analysis-only" if source.transcript_rights_attested else "blocked-missing-transcript-rights",
                "missing_safeguards": [] if source.transcript_rights_attested else ["transcript-rights-attestation"],
            })
    eligible_voice_sources = [
        record["source_id"] for record in records if record["decision"] == "eligible-for-private-corpus-intake"
    ]
    return {
        "report_type": "tts-training-source-registry-validation-v1",
        "contains_audio": False,
        "contains_transcripts": False,
        "contains_permission_document": False,
        "source_count": len(records),
        "roles": dict(sorted(roles.items())),
        "eligible_voice_training_source_ids": eligible_voice_sources,
        "training_decision": "private-corpus-intake-permitted" if eligible_voice_sources else "voice-training-blocked",
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate external TTS data source provenance")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with open(args.registry, encoding="utf-8") as source:
        registry = TtsSourceRegistry.model_validate_json(source.read())
    report = validate_tts_source_registry(registry)
    with open(args.output, "w", encoding="utf-8") as target:
        json.dump(report, target, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
