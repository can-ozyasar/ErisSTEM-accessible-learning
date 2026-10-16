"""Validate and unblind a private history punctuation listening response."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def evaluate(manifest_path: Path, mapping_path: Path, response_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    response = json.loads(response_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if manifest.get("experiment") != "same-run-punctuation-only-paired-v1" or mapping.get("input_sha256") != digest:
        raise ValueError("prosody_input_mismatch")
    pairs = mapping.get("assignments")
    item_ids = [item.get("id") for item in manifest.get("items", []) if isinstance(item, dict)]
    if not item_ids or len(item_ids) != len(manifest.get("items", [])) or any(not isinstance(item_id, str) for item_id in item_ids):
        raise ValueError("invalid_prosody_items")
    expected = {item_id.removesuffix("-control").removesuffix("-punctuation") for item_id in item_ids}
    if len(item_ids) != len(set(item_ids)) or set(item_ids) != {f"{item_id}-{variant}" for item_id in expected for variant in ("control", "punctuation")}:
        raise ValueError("invalid_prosody_pairs")
    if mapping.get("schema_version") != "tts-history-prosody-mapping-v1" or not isinstance(pairs, dict) or set(pairs) != expected or any(
        not isinstance(pair, dict) or set(pair) != {"A", "B"} or set(pair.values()) != {"control", "punctuation"}
        for pair in pairs.values()
    ):
        raise ValueError("invalid_prosody_mapping")
    entries = response.get("entries")
    reviewer = response.get("reviewer")
    if (response.get("schema_version") != "tts-history-prosody-listener-v1"
            or not isinstance(reviewer, str) or not reviewer.strip()
            or not isinstance(entries, list) or len(entries) != len(expected)):
        raise ValueError("invalid_prosody_response")
    if any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("invalid_prosody_entry")
    by_id = {entry.get("id"): entry for entry in entries}
    if len(by_id) != len(entries) or set(by_id) != expected:
        raise ValueError("invalid_prosody_ids")
    preference = Counter()
    accuracy = {"control": Counter(), "punctuation": Counter()}
    details = []
    for item_id in sorted(expected):
        entry = by_id[item_id]
        selected = entry.get("preferred")
        note = entry.get("note")
        if (selected not in {"A", "B", "equal"}
                or any(entry.get(f"accurate_{side.lower()}") not in {"yes", "no", "unsure"} for side in ("A", "B"))
                or not isinstance(note, str) or not 5 <= len(note.strip()) <= 500):
            raise ValueError("invalid_prosody_rating")
        winner = "equal" if selected == "equal" else pairs[item_id][selected]
        preference[winner] += 1
        for side in ("A", "B"):
            accuracy[pairs[item_id][side]][entry[f"accurate_{side.lower()}"]] += 1
        control_side = next(side for side in ("A", "B") if pairs[item_id][side] == "control")
        punctuation_side = "B" if control_side == "A" else "A"
        details.append({"id": item_id, "preferred_variant": winner,
                        "control_accuracy": entry[f"accurate_{control_side.lower()}"],
                        "punctuation_accuracy": entry[f"accurate_{punctuation_side.lower()}"],
                        "note": note.strip()})
    return {"schema_version": "tts-history-prosody-results-v1", "reviewer": reviewer,
            "input_sha256": digest, "pairs": len(expected), "preference": dict(preference),
            "accuracy": {name: dict(counts) for name, counts in accuracy.items()},
            "details": details, "student_publication": "blocked_pending_pronunciation_review"}


def evaluate_many(manifest_path: Path, mapping_path: Path, response_paths: list[Path]) -> dict:
    if not response_paths:
        raise ValueError("no_prosody_responses")
    reports = [evaluate(manifest_path, mapping_path, path) for path in response_paths]
    reviewers = [report["reviewer"] for report in reports]
    if len(reviewers) != len(set(reviewers)):
        raise ValueError("duplicate_prosody_reviewer_code")
    preference = Counter()
    accuracy = {"control": Counter(), "punctuation": Counter()}
    for report in reports:
        preference.update(report["preference"])
        for variant in accuracy:
            accuracy[variant].update(report["accuracy"][variant])
    return {"schema_version": "tts-history-prosody-aggregate-v1",
            "input_sha256": reports[0]["input_sha256"], "reviewer_codes": reviewers,
            "independent_listener_count_verified": False,
            "responses": len(reports), "pairs_per_response": reports[0]["pairs"],
            "preference": dict(preference),
            "accuracy": {variant: dict(counts) for variant, counts in accuracy.items()},
            "details": reports,
            "student_publication": "blocked_pending_pronunciation_review"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--responses", required=True, nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate_many(args.manifest, args.mapping, args.responses), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
