"""Prepare a sealed private WAV package for an ASR quality-screening run.

The input is accepted only when each downloaded Kaggle WAV matches the hash in
the original synthesis record.  The generated Dataset package contains no
reference spoken text or MEB material.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_AUDIO_FILES = 200


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def private_root() -> Path:
    return (repo_root() / "data" / "private").resolve()


def private_file(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(private_root()) or not resolved.is_file():
        raise ValueError("private_file_required")
    return resolved


def private_new_directory(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(private_root()) or resolved.exists():
        raise ValueError("new_private_output_directory_required")
    return resolved


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("invalid_private_json") from error
    if not isinstance(payload, dict):
        raise TypeError("private_json_object_required")
    return payload


def downloaded_audio(download_manifest_path: Path) -> tuple[str, dict[str, dict[str, object]]]:
    """Verify every downloaded WAV before it can enter an ASR package."""
    path = private_file(download_manifest_path)
    payload = _read_object(path)
    candidate, files = payload.get("candidate"), payload.get("files")
    if (
        payload.get("schema_version") != "kaggle-tts-audio-download-v1"
        or not isinstance(candidate, str)
        or not candidate
        or not isinstance(files, list)
        or not 1 <= len(files) <= MAX_AUDIO_FILES
    ):
        raise ValueError("invalid_tts_audio_download_manifest")
    root = path.parent.resolve()
    assets: dict[str, dict[str, object]] = {}
    for item in files:
        if not isinstance(item, dict):
            raise TypeError("invalid_downloaded_tts_audio_entry")
        item_id, relative_path, expected_hash, expected_bytes = (
            item.get("id"),
            item.get("path"),
            item.get("sha256"),
            item.get("bytes"),
        )
        if (
            not isinstance(item_id, str)
            or not ID_PATTERN.fullmatch(item_id)
            or not isinstance(relative_path, str)
            or not isinstance(expected_hash, str)
            or not SHA256_PATTERN.fullmatch(expected_hash)
            or not isinstance(expected_bytes, int)
            or expected_bytes <= 0
            or item_id in assets
        ):
            raise ValueError("invalid_downloaded_tts_audio_entry")
        source = (root / relative_path).resolve()
        if (
            not source.is_relative_to(root)
            or source.name != f"{item_id}.wav"
            or source.suffix.lower() != ".wav"
            or not source.is_file()
            or source.stat().st_size != expected_bytes
            or sha256(source) != expected_hash
        ):
            raise ValueError("downloaded_tts_audio_integrity_mismatch")
        assets[item_id] = {"source": source, "sha256": expected_hash}
    return candidate, assets


def synthesis_kinds(
    run_records_path: Path, candidate: str, expected_audio: dict[str, dict[str, object]]
) -> dict[str, str]:
    path = private_file(run_records_path)
    payload = _read_object(path)
    records = payload.get("records")
    if (
        payload.get("schema_version") != "tts-synthesis-run-v1"
        or payload.get("candidate") != candidate
        or not isinstance(records, list)
    ):
        raise ValueError("invalid_tts_synthesis_run_records")
    kinds: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("invalid_tts_synthesis_run_record")
        item_id, kind, status, audio_hash = (
            record.get("id"),
            record.get("kind"),
            record.get("status"),
            record.get("audio_sha256"),
        )
        if (
            not isinstance(item_id, str)
            or item_id in kinds
            or not isinstance(kind, str)
            or status != "generated"
            or not isinstance(audio_hash, str)
            or not SHA256_PATTERN.fullmatch(audio_hash)
        ):
            raise ValueError("invalid_tts_synthesis_run_record")
        kinds[item_id], hashes[item_id] = kind, audio_hash
    if set(kinds) != set(expected_audio) or any(
        hashes[item_id] != expected_audio[item_id]["sha256"] for item_id in expected_audio
    ):
        raise ValueError("tts_audio_ids_do_not_match_synthesis_run")
    return {item_id: kinds[item_id] for item_id in expected_audio}


def prepare_asr_input(download_manifest_path: Path, run_records_path: Path, output_dir: Path) -> dict[str, object]:
    candidate, audio = downloaded_audio(download_manifest_path)
    kinds = synthesis_kinds(run_records_path, candidate, audio)
    destination = private_new_directory(output_dir)
    audio_dir = destination / "audio"
    audio_dir.mkdir(parents=True)
    assets = []
    for item_id in sorted(audio):
        source = audio[item_id]["source"]
        target = audio_dir / f"{item_id}.wav"
        shutil.copy2(source, target)
        if sha256(target) != audio[item_id]["sha256"]:
            raise RuntimeError("copied_tts_audio_checksum_mismatch")
        assets.append(
            {
                "id": item_id,
                "kind": kinds[item_id],
                "audio_path": str(target.relative_to(destination)),
                "audio_sha256": audio[item_id]["sha256"],
            }
        )
    manifest = {
        "schema_version": "tts-asr-input-v1",
        "candidate": candidate,
        "source_download_manifest_sha256": sha256(private_file(download_manifest_path)),
        "source_synthesis_run_sha256": sha256(private_file(run_records_path)),
        "assets": assets,
    }
    (destination / "tts-asr-input.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "schema_version": manifest["schema_version"],
        "candidate": candidate,
        "audio_files": len(assets),
        "contains_reference_text": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare private checksum-verified WAV input for a TTS ASR run")
    parser.add_argument("--download-manifest", type=Path, required=True)
    parser.add_argument("--run-records", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = prepare_asr_input(args.download_manifest, args.run_records, args.output_dir)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
