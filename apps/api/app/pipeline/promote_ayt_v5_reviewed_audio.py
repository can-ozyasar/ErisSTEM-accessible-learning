"""Promote only explicitly human-reviewed AYT V5 audio units for runtime use."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

MODEL_SHA256 = "8ec3a3312b9586a8650c38d2c8e8e8b6214851f13afbaa935ed4c9d598af8503"
REVIEW_SCHEMA = "ayt-v5-human-listener-review-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid_{label}") from error
    if not isinstance(payload, dict):
        raise TypeError(f"invalid_{label}_root")
    return payload


def promote(input_manifest: Path, candidate_root: Path, review_path: Path, destination: Path) -> int:
    if destination.exists():
        raise FileExistsError("destination_already_exists")
    source = _load_json(input_manifest, "input_manifest")
    candidate = _load_json(candidate_root / "index.json", "candidate_index")
    review = _load_json(review_path, "listener_review")
    input_hash = sha256(input_manifest)
    if (source.get("schema_version") != "ayt-history-v5-static-audio-input-v1"
            or source.get("voice_model_sha256") != MODEL_SHA256
            or not isinstance(source.get("pack_checksum"), str)):
        raise ValueError("unsupported_or_unbound_input_manifest")
    source_hashes = candidate.get("source_sha256")
    if (candidate.get("schema_version") != "v5-demo-installed-v1"
            or candidate.get("model_sha256") != MODEL_SHA256
            or candidate.get("runtime_enabled") is not False
            or candidate.get("requires_listening_review") is not True
            or not isinstance(source_hashes, dict)
            or source_hashes.get("question") != source["pack_checksum"]
            or candidate.get("input_manifest_sha256") != input_hash):
        raise ValueError("candidate_package_binding_mismatch")
    if (review.get("schema") != REVIEW_SCHEMA
            or review.get("source_pack_sha256") != source["pack_checksum"]
            or review.get("input_manifest_sha256") != input_hash
            or review.get("voice_model_sha256") != MODEL_SHA256):
        raise ValueError("listener_review_binding_mismatch")
    reviewer = review.get("reviewer")
    reviewed_at = review.get("reviewed_at_utc")
    rows = review.get("items")
    if (not isinstance(reviewer, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", reviewer)
            or not isinstance(reviewed_at, str) or not reviewed_at.strip()):
        raise ValueError("listener_review_provenance_missing")
    if not isinstance(rows, list) or not rows:
        raise ValueError("listener_review_items_missing")

    input_items = source.get("items")
    candidate_items = candidate.get("items")
    if not isinstance(input_items, list) or not isinstance(candidate_items, list):
        raise TypeError("invalid_candidate_items")
    valid_text_hashes: set[str] = set()
    for item in input_items:
        if not isinstance(item, dict) or not isinstance(item.get("spoken_text"), str):
            raise TypeError("invalid_input_audio_item")
        text_hash = item.get("spoken_text_sha256")
        actual_hash = hashlib.sha256(item["spoken_text"].encode("utf-8")).hexdigest()
        if (text_hash != actual_hash or item.get("contains_digits") is not False
                or any(char.isdigit() for char in item["spoken_text"])):
            raise ValueError("input_audio_item_checksum_or_scope_invalid")
        valid_text_hashes.add(text_hash)
    assets_by_text: dict[str, list[dict]] = {}
    for item in candidate_items:
        if not isinstance(item, dict):
            raise TypeError("invalid_candidate_item")
        text_hash = item.get("spoken_text_sha256")
        if text_hash not in valid_text_hashes:
            raise ValueError("candidate_contains_unbound_text")
        assets_by_text.setdefault(text_hash, []).append(item)

    decisions: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("invalid_listener_review_item")
        text_hash = row.get("spoken_text_sha256")
        if (not isinstance(text_hash, str) or len(text_hash) != 64
                or any(char not in "0123456789abcdef" for char in text_hash)
                or text_hash not in valid_text_hashes or text_hash in decisions):
            raise ValueError("listener_review_text_identity_invalid")
        if (row.get("intelligibility") not in {"pass", "fail"}
                or row.get("pronunciation") not in {"pass", "fail"}
                or row.get("audio_artifacts") not in {"none", "minor", "major"}
                or row.get("decision") not in {"accept", "reject"}):
            raise ValueError("listener_review_rubric_invalid")
        accepted = (row["decision"] == "accept" and row["intelligibility"] == "pass"
                    and row["pronunciation"] == "pass" and row["audio_artifacts"] == "none")
        if row["decision"] == "accept" and not accepted:
            raise ValueError("accept_requires_all_quality_checks_to_pass")
        decisions[text_hash] = "accept" if accepted else "reject"
    accepted_hashes = {text_hash for text_hash, decision in decisions.items() if decision == "accept"}
    if not accepted_hashes:
        raise ValueError("no_audio_units_approved")

    for text_hash in accepted_hashes:
        if text_hash not in assets_by_text:
            raise ValueError("approved_audio_missing_from_candidate")
    selected = [item for item in candidate_items if item["spoken_text_sha256"] in accepted_hashes]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ayt-v5-approved-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "package"
        (staging / "audio").mkdir(parents=True)
        copied: set[str] = set()
        for item in selected:
            filename = item.get("filename")
            relative = Path(filename) if isinstance(filename, str) else Path("invalid")
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("candidate_audio_path_invalid")
            source_audio = (candidate_root / relative).resolve()
            if not source_audio.is_relative_to(candidate_root.resolve()) or not source_audio.is_file():
                raise ValueError("candidate_audio_missing")
            if source_audio.stat().st_size != item.get("bytes") or sha256(source_audio) != item.get("audio_sha256"):
                raise ValueError("candidate_audio_checksum_mismatch")
            with source_audio.open("rb") as stream:
                header = stream.read(12)
            if len(header) != 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
                raise ValueError("candidate_audio_invalid_wav")
            digest = item["spoken_text_sha256"]
            target = staging / "audio" / f"{digest}.wav"
            if digest not in copied:
                shutil.copyfile(source_audio, target)
                copied.add(digest)
        review_hash = sha256(review_path)
        index = {
            "schema_version": "v5-demo-installed-v1",
            "model_sha256": MODEL_SHA256,
            "source_sha256": {"question": source["pack_checksum"]},
            "input_manifest_sha256": input_hash,
            "runtime_enabled": True,
            "requires_listening_review": False,
            "listener_review": {
                "schema": REVIEW_SCHEMA,
                "review_sha256": review_hash,
                "reviewer": reviewer.strip(),
                "reviewed_at_utc": reviewed_at,
                "approved_unique_texts": len(accepted_hashes),
                "approved_units": len(selected),
            },
            "items": selected,
        }
        (staging / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.rename(destination)
    return len(selected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(f"Promoted {promote(args.input_manifest, args.candidate_root, args.review, args.destination)} reviewed audio units.")


if __name__ == "__main__":
    main()
