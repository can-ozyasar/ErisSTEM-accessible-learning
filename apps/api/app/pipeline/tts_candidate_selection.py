"""Fail-closed selection report for content-free TTS quality reports."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_quality_report(path: Path) -> dict[str, object]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("invalid_tts_quality_report") from error
    if (
        not isinstance(report, dict)
        or report.get("report_type") != "tts-quality-evaluation-v1"
        or report.get("contains_document_content") is not False
        or not isinstance(report.get("candidate"), str)
        or not isinstance(report.get("decision"), str)
        or not isinstance(report.get("eligible_kinds"), list)
        or not isinstance(report.get("kind_results"), dict)
    ):
        raise ValueError("invalid_tts_quality_report")
    return report


def select_tts_candidates(reports: list[tuple[Path, dict[str, object]]]) -> dict[str, object]:
    """Select only listener-study-eligible kinds; fail closed for all others."""
    candidates: list[dict[str, object]] = []
    seen = set()
    for path, report in reports:
        candidate = str(report["candidate"])
        if candidate in seen:
            raise ValueError("duplicate_tts_candidate_report")
        seen.add(candidate)
        eligible = sorted(str(kind) for kind in report["eligible_kinds"])
        candidates.append(
            {
                "candidate": candidate,
                "quality_report_sha256": sha256(path),
                "decision": report["decision"],
                "eligible_kinds": eligible,
                "pronunciation_accuracy": report.get("pronunciation_accuracy"),
                "critical_token_accuracy": report.get("critical_token_accuracy"),
            }
        )
    eligible = [candidate for candidate in candidates if candidate["eligible_kinds"]]
    return {
        "report_type": "tts-candidate-selection-v1",
        "contains_document_content": False,
        "candidates": candidates,
        "selection": (
            "no_candidate_eligible"
            if not eligible
            else "listener_study_required_before_any_audio_asset"
        ),
        "eligible_candidate_count": len(eligible),
        "next_action": (
            "diagnose_error_clusters_and_compare_a_new_candidate"
            if not eligible
            else "run_blind_listener_study_only_for_eligible_kinds"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a fail-closed private TTS candidate-selection report")
    parser.add_argument("--quality-report", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing_to_overwrite_tts_candidate_selection_report")
    reports = [(path, _read_quality_report(path)) for path in args.quality_report]
    report = select_tts_candidates(reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("report_type", "selection", "eligible_candidate_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
