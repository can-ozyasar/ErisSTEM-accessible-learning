"""Private intake validation for consented Turkish STEM TTS training recordings.

The validator does not inspect linguistic quality or train a model. It rejects
unsafe paths and structurally unsuitable WAV input, then writes a content-free
report so collection can be audited without exposing a speaker or lesson text.
"""

from __future__ import annotations

import argparse
import json
import wave
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

VALID_KINDS = {"text", "formula", "table", "chart", "exercise"}
VALID_SPLITS = {"train", "validation"}
MIN_SAMPLE_RATE = 22_050
MIN_RECORDING_SECONDS = 0.8
MAX_RECORDING_SECONDS = 30.0


class VoiceCorpusConsent(BaseModel):
    """Attestations stored without a legal name, contact detail, or recording text."""

    model_config = ConfigDict(extra="forbid")

    speaker_reference: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    source: str = Field(pattern=r"^(self-recorded|written-licensed)$")
    adult_consent_attested: bool
    voice_model_training_consent_attested: bool
    withdrawal_process_available: bool

    @model_validator(mode="after")
    def require_all_safeguards(self) -> VoiceCorpusConsent:
        if not (
            self.adult_consent_attested
            and self.voice_model_training_consent_attested
            and self.withdrawal_process_available
        ):
            raise ValueError("incomplete_voice_training_consent")
        return self


class VoiceCorpusRecording(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    audio_path: str = Field(min_length=5, max_length=512)
    transcript: str = Field(min_length=1, max_length=8_000)
    kind: str
    split: str

    @model_validator(mode="after")
    def bounded_fields(self) -> VoiceCorpusRecording:
        path = Path(self.audio_path)
        if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".wav":
            raise ValueError("unsafe_or_unsupported_audio_path")
        if self.kind not in VALID_KINDS:
            raise ValueError("invalid_tts_kind")
        if self.split not in VALID_SPLITS:
            raise ValueError("invalid_tts_split")
        return self


class VoiceTrainingCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    consent: VoiceCorpusConsent
    recordings: list[VoiceCorpusRecording] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids_and_paths(self) -> VoiceTrainingCorpus:
        ids = [record.id for record in self.recordings]
        paths = [record.audio_path for record in self.recordings]
        if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
            raise ValueError("voice_corpus_ids_and_paths_must_be_unique")
        return self


def _wav_details(path: Path) -> dict[str, float | int]:
    try:
        with wave.open(str(path), "rb") as audio:
            channels, sample_rate = audio.getnchannels(), audio.getframerate()
            sample_width, frames, compression = audio.getsampwidth(), audio.getnframes(), audio.getcomptype()
    except (OSError, wave.Error) as error:
        raise ValueError("unreadable_wav") from error
    if compression != "NONE" or channels != 1 or sample_rate < MIN_SAMPLE_RATE or sample_width < 2:
        raise ValueError("unsupported_wav_format")
    duration = frames / sample_rate if sample_rate else 0.0
    if not MIN_RECORDING_SECONDS <= duration <= MAX_RECORDING_SECONDS:
        raise ValueError("recording_duration_out_of_bounds")
    return {"sample_rate": sample_rate, "sample_width": sample_width, "duration_seconds": duration}


def validate_voice_training_corpus(corpus: VoiceTrainingCorpus, audio_root: Path) -> dict:
    """Validate private WAVs and emit no transcript, path, or speaker identity."""
    if corpus.schema_version != "tts-training-corpus-v1":
        raise ValueError("invalid_voice_training_corpus_schema")
    root = audio_root.resolve()
    if not root.is_dir():
        raise ValueError("audio_root_not_found")
    split_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    sample_rates: Counter[int] = Counter()
    sample_widths: Counter[int] = Counter()
    total_seconds = 0.0
    for record in corpus.recordings:
        audio_path = (root / record.audio_path).resolve()
        if not audio_path.is_relative_to(root) or not audio_path.is_file():
            raise ValueError("recording_outside_audio_root_or_missing")
        details = _wav_details(audio_path)
        split_counts[record.split] += 1
        kind_counts[record.kind] += 1
        sample_rates[int(details["sample_rate"])] += 1
        sample_widths[int(details["sample_width"])] += 1
        total_seconds += float(details["duration_seconds"])
    if not split_counts["train"] or not split_counts["validation"]:
        raise ValueError("train_and_validation_splits_required")
    return {
        "report_type": "tts-training-corpus-validation-v1",
        "contains_audio": False,
        "contains_transcripts": False,
        "consent_attested": True,
        "recordings": len(corpus.recordings),
        "duration_seconds": round(total_seconds, 3),
        "splits": dict(sorted(split_counts.items())),
        "kinds": dict(sorted(kind_counts.items())),
        "sample_rates": dict(sorted(sample_rates.items())),
        "sample_widths": dict(sorted(sample_widths.items())),
        "decision": "corpus-structure-valid-requires-model-specific-data-audit",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a private consented TTS training corpus")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus = VoiceTrainingCorpus.model_validate_json(args.manifest.read_text(encoding="utf-8"))
    report = validate_voice_training_corpus(corpus, args.audio_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
