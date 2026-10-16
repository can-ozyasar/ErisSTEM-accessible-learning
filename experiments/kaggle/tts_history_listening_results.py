"""Validate and unblind the private history TTS listening pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def evaluate(manifest_path: Path, mapping_path: Path, response_paths: list[Path]) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if mapping.get("input_sha256") != hashlib.sha256(manifest_path.read_bytes()).hexdigest():
        raise ValueError("history_input_checksum_mismatch")
    if manifest.get("schema_version") != "tts-history-eval-v1":
        raise ValueError("invalid_history_manifest")
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("invalid_history_items")
    ids = [item.get("id") for item in items]
    if any(not isinstance(item_id, str) for item_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid_history_ids")
    assignments = mapping.get("assignments")
    if not isinstance(assignments, dict) or set(assignments) != set(ids) or any(
        not isinstance(pair, dict) or set(pair) != {"A", "B"} or set(pair.values()) != {"piper", "chatterbox"}
        for pair in assignments.values()
    ):
        raise ValueError("invalid_blind_mapping")
    if not response_paths:
        raise ValueError("no_listener_responses")

    reviewers: set[str] = set()
    preferences: Counter[str] = Counter()
    accuracy: dict[str, Counter[str]] = {model: Counter() for model in ("piper", "chatterbox")}
    kind_preferences: dict[str, Counter[str]] = {}
    notes: list[dict[str, str]] = []
    for response_path in response_paths:
        response = json.loads(response_path.read_text(encoding="utf-8"))
        reviewer = response.get("reviewer")
        entries = response.get("entries")
        if response.get("schema_version") != "tts-history-listener-v1" or not isinstance(reviewer, str) or not reviewer.strip() or reviewer in reviewers:
            raise ValueError("invalid_or_duplicate_reviewer")
        if not isinstance(entries, list) or len(entries) != len(ids):
            raise ValueError("incomplete_listener_response")
        by_id = {entry.get("id"): entry for entry in entries if isinstance(entry, dict)}
        if len(by_id) != len(ids) or set(by_id) != set(ids):
            raise ValueError("mismatched_listener_ids")
        reviewers.add(reviewer)
        for item in items:
            item_id = item["id"]
            entry = by_id[item_id]
            preferred = entry.get("preferred")
            if preferred not in {"A", "B", "equal"} or any(entry.get(key) not in {"yes", "no", "unsure"} for key in ("accurate_a", "accurate_b")):
                raise ValueError("invalid_listener_rating")
            winner = "equal" if preferred == "equal" else assignments[item_id][preferred]
            preferences[winner] += 1
            kind_preferences.setdefault(str(item.get("kind")), Counter())[winner] += 1
            for label in ("A", "B"):
                accuracy[assignments[item_id][label]][entry[f"accurate_{label.lower()}"]] += 1
            note = entry.get("note", "")
            if not isinstance(note, str) or len(note) > 500:
                raise ValueError("invalid_listener_note")
            if note.strip():
                notes.append({"reviewer": reviewer, "id": item_id, "note": note.strip()})
    return {
        "schema_version": "tts-history-listening-results-v1",
        "input_sha256": mapping.get("input_sha256"),
        "reviewers": sorted(reviewers),
        "items_per_reviewer": len(ids),
        "preferences": dict(preferences),
        "accuracy": {model: dict(counts) for model, counts in accuracy.items()},
        "preferences_by_kind": {kind: dict(counts) for kind, counts in kind_preferences.items()},
        "notes": notes,
        "student_publication": "blocked_pending_independent_listeners_and_accessibility_test",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--responses", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.manifest, args.mapping, args.responses), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
