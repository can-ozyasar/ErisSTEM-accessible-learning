"""Validate and unblind the private source-letter pronunciation A/B response."""

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
    items = manifest.get("items")
    if (manifest.get("experiment") != "same-run-source-label-pronunciation-v1"
            or not isinstance(items, list) or not items
            or mapping.get("schema_version") != "tts-history-pronunciation-mapping-v1"
            or mapping.get("input_sha256") != digest):
        raise ValueError("pronunciation_input_mismatch")
    item_ids = [item.get("id") for item in items if isinstance(item, dict)]
    if len(item_ids) != len(items) or any(not isinstance(item_id, str) for item_id in item_ids):
        raise ValueError("invalid_pronunciation_items")
    pairs = {item_id.removesuffix("-control").removesuffix("-normalized") for item_id in item_ids}
    if len(item_ids) != len(set(item_ids)) or set(item_ids) != {f"{pair}-{variant}" for pair in pairs for variant in ("control", "normalized")}:
        raise ValueError("invalid_pronunciation_pairs")
    assignments = mapping.get("assignments")
    if not isinstance(assignments, dict) or set(assignments) != pairs or any(
        not isinstance(value, dict) or set(value) != {"A", "B"} or set(value.values()) != {"control", "normalized"}
        for value in assignments.values()
    ):
        raise ValueError("invalid_pronunciation_mapping")
    entries = response.get("entries")
    reviewer = response.get("reviewer")
    if (response.get("schema_version") != "tts-history-pronunciation-listener-v1"
            or not isinstance(reviewer, str) or not reviewer.strip()
            or not isinstance(entries, list) or len(entries) != len(pairs)
            or any(not isinstance(entry, dict) for entry in entries)):
        raise ValueError("invalid_pronunciation_response")
    by_id = {entry.get("id"): entry for entry in entries}
    if len(by_id) != len(entries) or set(by_id) != pairs:
        raise ValueError("invalid_pronunciation_ids")
    preference = Counter()
    accuracy = {"control": Counter(), "normalized": Counter()}
    details = []
    for pair in sorted(pairs):
        entry = by_id[pair]
        selected, note = entry.get("preferred"), entry.get("note")
        if (selected not in {"A", "B", "equal"}
                or any(entry.get(f"accurate_{side.lower()}") not in {"yes", "no", "unsure"} for side in ("A", "B"))
                or not isinstance(note, str) or not 5 <= len(note.strip()) <= 500):
            raise ValueError("invalid_pronunciation_rating")
        preferred_variant = "equal" if selected == "equal" else assignments[pair][selected]
        preference[preferred_variant] += 1
        for side in ("A", "B"):
            accuracy[assignments[pair][side]][entry[f"accurate_{side.lower()}"]] += 1
        control_side = next(side for side in ("A", "B") if assignments[pair][side] == "control")
        normalized_side = "B" if control_side == "A" else "A"
        details.append({"id": pair, "preferred_variant": preferred_variant,
                        "control_accuracy": entry[f"accurate_{control_side.lower()}"],
                        "normalized_accuracy": entry[f"accurate_{normalized_side.lower()}"],
                        "note": note.strip()})
    return {"schema_version": "tts-history-pronunciation-results-v1", "reviewer": reviewer,
            "input_sha256": digest, "pairs": len(pairs), "preference": dict(preference),
            "accuracy": {name: dict(counts) for name, counts in accuracy.items()},
            "details": details, "student_publication": "blocked_pending_independent_listeners"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--response", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.manifest, args.mapping, args.response), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
