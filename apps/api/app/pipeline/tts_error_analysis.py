"""Content-free diagnostics for private Turkish STEM TTS ASR screens.

The report deliberately contains neither the Gold references nor ASR
transcripts.  It is a prioritisation aid for choosing the next experiment,
never evidence that a candidate may be published.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .tts_text_metrics import speech_character_accuracy, speech_tokens
from .tts_quality import TtsCandidateManifest, TtsGoldManifest

ACCURACY_BANDS = ((0.85, "below_85"), (0.95, "85_to_95"), (1.0, "95_to_100"))


def _tokens(value: str) -> list[str]:
    return speech_tokens(value)


def _band(accuracy: float) -> str:
    for upper_bound, name in ACCURACY_BANDS:
        if accuracy < upper_bound:
            return name
    return "exact"


def analyse_tts_errors(gold: TtsGoldManifest, candidate: TtsCandidateManifest) -> dict[str, object]:
    """Aggregate error severity by content kind without exposing lesson text."""
    if gold.schema_version != "tts-gold-v1" or candidate.schema_version != "tts-candidate-v1":
        raise ValueError("invalid_tts_analysis_schema")
    actual = {item.id: item for item in candidate.results}
    by_kind: dict[str, dict[str, object]] = {
        kind: {
            "samples": 0,
            "missing_transcripts": 0,
            "exact_transcripts": 0,
            "critical_token_complete_samples": 0,
            "critical_token_total": 0,
            "critical_token_matched": 0,
            "accuracy_bands": Counter(),
        }
        for kind in ("text", "formula", "table", "chart", "exercise")
    }
    for item in gold.items:
        summary = by_kind[item.kind]
        summary["samples"] = int(summary["samples"]) + 1
        expected_critical = Counter(token for value in item.critical_tokens for token in _tokens(value))
        summary["critical_token_total"] = int(summary["critical_token_total"]) + sum(expected_critical.values())
        result = actual.get(item.id)
        if result is None:
            summary["missing_transcripts"] = int(summary["missing_transcripts"]) + 1
            summary["accuracy_bands"]["missing"] += 1  # type: ignore[index]
            continue
        accuracy = speech_character_accuracy(item.expected_spoken_text, result.observed_spoken_text)
        observed_critical = Counter(_tokens(result.observed_spoken_text))
        matched = sum((expected_critical & observed_critical).values())
        summary["critical_token_matched"] = int(summary["critical_token_matched"]) + matched
        if matched == sum(expected_critical.values()):
            summary["critical_token_complete_samples"] = int(summary["critical_token_complete_samples"]) + 1
        if accuracy == 1.0:
            summary["exact_transcripts"] = int(summary["exact_transcripts"]) + 1
        summary["accuracy_bands"][_band(accuracy)] += 1  # type: ignore[index]

    kinds: dict[str, dict[str, object]] = {}
    priority = []
    for kind, summary in by_kind.items():
        total = int(summary["critical_token_total"])
        matched = int(summary["critical_token_matched"])
        samples = int(summary["samples"])
        missing_critical = total - matched
        critical_accuracy = matched / total if total else 1.0
        kinds[kind] = {
            "samples": samples,
            "missing_transcripts": int(summary["missing_transcripts"]),
            "exact_transcripts": int(summary["exact_transcripts"]),
            "critical_token_complete_samples": int(summary["critical_token_complete_samples"]),
            "critical_token_accuracy": critical_accuracy,
            "accuracy_bands": dict(sorted(summary["accuracy_bands"].items())),  # type: ignore[union-attr]
        }
        # Priority combines a concrete critical-token loss with broad ASR
        # divergence. It only orders investigation work; it is not a score for
        # choosing a student-facing voice.
        priority.append((missing_critical, samples - int(summary["exact_transcripts"]), kind))
    priority.sort(reverse=True)
    return {
        "report_type": "tts-error-analysis-v1",
        "contains_document_content": False,
        "candidate": candidate.candidate,
        "gold_samples": len(gold.items),
        "unexpected_candidate_ids": sorted(set(actual) - {item.id for item in gold.items}),
        "kinds": kinds,
        "investigation_priority": [kind for _, _, kind in priority],
        "decision": "diagnostic-only-not-a-publication-decision",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a content-free private TTS error analysis")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing_to_overwrite_tts_error_analysis")
    try:
        gold = TtsGoldManifest.model_validate_json(args.gold.read_text(encoding="utf-8"))
        candidate = TtsCandidateManifest.model_validate_json(args.candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("invalid_or_missing_private_tts_error_analysis_input") from error
    report = analyse_tts_errors(gold, candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("report_type", "candidate", "decision")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
