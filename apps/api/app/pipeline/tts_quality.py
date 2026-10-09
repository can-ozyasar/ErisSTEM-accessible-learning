"""Private evaluation gate for Turkish STEM TTS candidates and fine-tuning.

Audio files and reference content remain private. This module produces only
content-free aggregate metrics and cannot approve a voice by preference alone.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .tts_text_metrics import speech_character_accuracy, speech_tokens

MIN_TTS_GOLD_SAMPLES = 50
MIN_KIND_GOLD_SAMPLES = 10
QUALITY_POLICY_VERSION = "tts-quality-policy-v3"

# These are *screening* thresholds, rather than a claim that ASR is a perfect
# proxy for learner comprehension.  Passing only permits a blind listener
# study for the particular content kinds listed below; it never publishes an
# audio asset.  Formulae deliberately retain the strictest critical-token
# threshold because a changed operator can change the lesson meaning.
KIND_SCREENING_THRESHOLDS: dict[str, dict[str, float]] = {
    "text": {"pronunciation_accuracy": 0.98, "critical_token_accuracy": 0.95},
    "exercise": {"pronunciation_accuracy": 0.96, "critical_token_accuracy": 0.97},
    "table": {"pronunciation_accuracy": 0.95, "critical_token_accuracy": 0.97},
    "chart": {"pronunciation_accuracy": 0.95, "critical_token_accuracy": 0.97},
    "formula": {"pronunciation_accuracy": 0.95, "critical_token_accuracy": 0.98},
}


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
    evaluation_scope: Literal["calibration", "source-bound-release"] = "calibration"
    items: list[TtsGoldItem] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self) -> TtsGoldManifest:
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("TTS Gold ids must be unique")
        for item in self.items:
            expected = Counter(speech_tokens(item.expected_spoken_text))
            critical = Counter(token for phrase in item.critical_tokens for token in speech_tokens(phrase))
            if not critical or critical - expected:
                raise ValueError("TTS Gold critical tokens must occur in the reference reading")
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
    return speech_tokens(value)


def evaluate_tts_candidate(gold: TtsGoldManifest, candidate: TtsCandidateManifest) -> dict:
    """Report pronunciation and critical-token metrics without exposing lesson text."""
    if gold.schema_version != "tts-gold-v1" or candidate.schema_version != "tts-candidate-v1":
        raise ValueError("invalid TTS evaluation schema")
    actual = {item.id: item for item in candidate.results}
    records, pronunciation_scores, critical_total, critical_exact = [], [], 0, 0
    by_kind: dict[str, dict[str, float | int]] = {
        kind: {
            "gold_samples": 0,
            "pronunciation_total": 0.0,
            "critical_token_total": 0,
            "critical_token_exact": 0,
        }
        for kind in KIND_SCREENING_THRESHOLDS
    }
    for item in gold.items:
        summary = by_kind[item.kind]
        summary["gold_samples"] = int(summary["gold_samples"]) + 1
        result = actual.get(item.id)
        if result is None:
            records.append({"id": item.id, "kind": item.kind, "status": "missing"})
            pronunciation_scores.append(0.0)
            critical_total += len(item.critical_tokens)
            summary["critical_token_total"] = int(summary["critical_token_total"]) + len(item.critical_tokens)
            continue
        accuracy = speech_character_accuracy(item.expected_spoken_text, result.observed_spoken_text)
        observed_tokens = Counter(_tokens(result.observed_spoken_text))
        expected_tokens = Counter(token for value in item.critical_tokens for token in _tokens(value))
        exact = sum((observed_tokens & expected_tokens).values())
        total = sum(expected_tokens.values())
        critical_total += total
        critical_exact += exact
        pronunciation_scores.append(accuracy)
        summary["pronunciation_total"] = float(summary["pronunciation_total"]) + accuracy
        summary["critical_token_total"] = int(summary["critical_token_total"]) + total
        summary["critical_token_exact"] = int(summary["critical_token_exact"]) + exact
        records.append({"id": item.id, "kind": item.kind, "status": "scored", "pronunciation_accuracy": accuracy, "critical_tokens_exact": exact == total})
    unexpected = sorted(set(actual) - {item.id for item in gold.items})
    pronunciation = sum(pronunciation_scores) / len(gold.items)
    critical_accuracy = critical_exact / critical_total if critical_total else 1.0
    complete = not unexpected and len(actual) == len(gold.items)
    kind_results: dict[str, dict[str, object]] = {}
    eligible_kinds: list[str] = []
    for kind, thresholds in KIND_SCREENING_THRESHOLDS.items():
        summary = by_kind[kind]
        sample_count = int(summary["gold_samples"])
        kind_pronunciation = float(summary["pronunciation_total"]) / sample_count if sample_count else 0.0
        kind_critical_total = int(summary["critical_token_total"])
        kind_critical_accuracy = (
            int(summary["critical_token_exact"]) / kind_critical_total if kind_critical_total else 1.0
        )
        reasons = []
        if sample_count < MIN_KIND_GOLD_SAMPLES:
            reasons.append("insufficient_kind_gold_samples")
        if not complete:
            reasons.append("incomplete_or_unexpected_candidate_results")
        if kind_pronunciation < thresholds["pronunciation_accuracy"]:
            reasons.append("pronunciation_below_kind_threshold")
        if kind_critical_accuracy < thresholds["critical_token_accuracy"]:
            reasons.append("critical_tokens_below_kind_threshold")
        passed = not reasons
        if passed:
            eligible_kinds.append(kind)
        kind_results[kind] = {
            "gold_samples": sample_count,
            "minimum_gold_samples": MIN_KIND_GOLD_SAMPLES,
            "pronunciation_accuracy": kind_pronunciation,
            "critical_token_accuracy": kind_critical_accuracy,
            "thresholds": thresholds,
            "automatic_screen": "passed" if passed else "blocked",
            "block_reasons": reasons,
        }
    if len(gold.items) < MIN_TTS_GOLD_SAMPLES:
        eligible_kinds = []
    decision = (
        "tts-candidate-blocked"
        if not eligible_kinds
        else "tts-candidate-passed-listener-study-required"
        if len(eligible_kinds) == len(KIND_SCREENING_THRESHOLDS)
        else "tts-candidate-kind-limited-listener-study-required"
    )
    return {
        "report_type": "tts-quality-evaluation-v1",
        "contains_document_content": False,
        "quality_policy_version": QUALITY_POLICY_VERSION,
        "evaluation_scope": gold.evaluation_scope,
        "candidate": candidate.candidate,
        "gold_samples": len(gold.items),
        "minimum_gold_samples": MIN_TTS_GOLD_SAMPLES,
        "pronunciation_accuracy": pronunciation,
        "critical_token_accuracy": critical_accuracy,
        "unexpected_candidate_ids": unexpected,
        "kind_results": kind_results,
        "eligible_kinds": eligible_kinds,
        "decision": decision,
        "records": records,
    }


def main() -> int:
    """Score private ASR or human-reviewed transcripts without exposing them."""
    parser = argparse.ArgumentParser(description="Evaluate a private Turkish STEM TTS candidate")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing_to_overwrite_tts_quality_report")
    try:
        gold = TtsGoldManifest.model_validate_json(args.gold.read_text(encoding="utf-8"))
        candidate = TtsCandidateManifest.model_validate_json(args.candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("invalid_or_missing_private_tts_evaluation_input") from error
    report = evaluate_tts_candidate(gold, candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("report_type", "candidate", "gold_samples", "decision")
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
