"""Private evaluation gate for Turkish STEM TTS candidates and fine-tuning.

Audio files and reference content remain private. This module produces only
content-free aggregate metrics and cannot approve a voice by preference alone.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .benchmark import character_error_rate, normalized

MIN_TTS_GOLD_SAMPLES = 50
MIN_PRONUNCIATION_ACCURACY = 0.98
MIN_CRITICAL_TOKEN_ACCURACY = 1.0


class TtsGoldItem(BaseModel):
    """Private utterance reference; text/audio are intentionally not persisted in reports."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    expected_spoken_text: str = Field(min_length=1, max_length=8000)
    critical_tokens: list[str] = Field(default_factory=list, max_length=100)
    kind: str = Field(pattern=r"^(text|formula|table|chart|exercise)$")


class TtsGoldManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    items: list[TtsGoldItem] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self) -> TtsGoldManifest:
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("TTS Gold ids must be unique")
        return self


class TtsCandidateResult(BaseModel):
    """ASR/human-reviewed transcript of a candidate voice, held only privately."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    observed_spoken_text: str = Field(min_length=1, max_length=8000)


class TtsCandidateManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    candidate: str = Field(min_length=1, max_length=100)
    results: list[TtsCandidateResult]

    @model_validator(mode="after")
    def unique_ids(self) -> TtsCandidateManifest:
        ids = [item.id for item in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("TTS candidate ids must be unique")
        return self


def _tokens(value: str) -> list[str]:
    return normalized(value).split()


def evaluate_tts_candidate(gold: TtsGoldManifest, candidate: TtsCandidateManifest) -> dict:
    """Report pronunciation and critical-token metrics without exposing lesson text."""
    if gold.schema_version != "tts-gold-v1" or candidate.schema_version != "tts-candidate-v1":
        raise ValueError("invalid TTS evaluation schema")
    actual = {item.id: item for item in candidate.results}
    records, pronunciation_scores, critical_total, critical_exact = [], [], 0, 0
    for item in gold.items:
        result = actual.get(item.id)
        if result is None:
            records.append({"id": item.id, "kind": item.kind, "status": "missing"})
            pronunciation_scores.append(0.0)
            critical_total += len(item.critical_tokens)
            continue
        accuracy = 1 - character_error_rate(item.expected_spoken_text, result.observed_spoken_text)
        observed_tokens = Counter(_tokens(result.observed_spoken_text))
        expected_tokens = Counter(token for value in item.critical_tokens for token in _tokens(value))
        exact = sum((observed_tokens & expected_tokens).values())
        total = sum(expected_tokens.values())
        critical_total += total
        critical_exact += exact
        pronunciation_scores.append(accuracy)
        records.append({"id": item.id, "kind": item.kind, "status": "scored", "pronunciation_accuracy": accuracy, "critical_tokens_exact": exact == total})
    unexpected = sorted(set(actual) - {item.id for item in gold.items})
    pronunciation = sum(pronunciation_scores) / len(gold.items)
    critical_accuracy = critical_exact / critical_total if critical_total else 1.0
    complete = not unexpected and len(actual) == len(gold.items)
    passed = (
        len(gold.items) >= MIN_TTS_GOLD_SAMPLES
        and complete
        and pronunciation >= MIN_PRONUNCIATION_ACCURACY
        and critical_accuracy >= MIN_CRITICAL_TOKEN_ACCURACY
    )
    return {
        "report_type": "tts-quality-evaluation-v1",
        "contains_document_content": False,
        "candidate": candidate.candidate,
        "gold_samples": len(gold.items),
        "minimum_gold_samples": MIN_TTS_GOLD_SAMPLES,
        "pronunciation_accuracy": pronunciation,
        "critical_token_accuracy": critical_accuracy,
        "unexpected_candidate_ids": unexpected,
        "decision": "tts-candidate-passed-listener-study-required" if passed else "tts-candidate-blocked",
        "records": records,
    }
