"""Inventory exact installed V5 audio matches for a local AYT exam pack."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.demo_audio import MODEL_SHA256, _resolve_at
from app.exam_practice import AytHistoryExamPack
from app.pipeline.prepare_ayt_history_v5_audio_manifest import build


def audit(pack_path: Path, roots: list[Path]) -> dict:
    raw = pack_path.read_bytes()
    manifest = build(AytHistoryExamPack.model_validate_json(raw), hashlib.sha256(raw).hexdigest())
    counts: Counter[tuple[str, str]] = Counter()
    for row in manifest["items"]:
        role = row["static_role"]
        if row["kind"] == "interface":
            identifier = hashlib.sha256(row["spoken_text"].encode()).hexdigest()
            found = any(_resolve_at(root.resolve(), "interface", identifier, row["spoken_text"], None) is not None for root in roots)
        elif row["kind"] == "question":
            found = any(_resolve_at(root.resolve(), "question", row["id"], row["spoken_text"], pack_path.resolve()) is not None
                        for root in roots)
        else:
            raise ValueError("unexpected_audio_kind")
        status = "verified_audio" if found else "missing_audio"
        counts[(role, status)] += 1
    units = len(manifest["items"])
    verified = sum(count for (role, status), count in counts.items() if status == "verified_audio")
    repository = Path(__file__).resolve().parents[4]
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True,
                                capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {"schema": "ayt-static-audio-inventory-v1", "pack_sha256": hashlib.sha256(raw).hexdigest(),
            "voice_model_sha256": MODEL_SHA256, "question_count": manifest["summary"]["questions"],
            "static_unit_count": units, "verified_audio_count": verified, "missing_audio_count": units - verified,
            "verified_audio_fraction": round(verified / units, 6) if units else 1.0,
            "git_commit": commit, "evaluated_at_utc": datetime.now(UTC).isoformat(),
            "summary": {role: {status: count for (kind, status), count in counts.items() if kind == role}
                        for role in sorted({kind for kind, _ in counts})},
            "digits_require_pronunciation_review": manifest["summary"]["units_with_digits_withheld"],
            "notice": "A match requires exact package, model, text, audio checksum, RIFF/WAVE validation and unit identity."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.pack, args.root)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError("refusing_to_overwrite_audio_inventory_report")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
        print(json.dumps({key: result[key] for key in (
            "question_count", "static_unit_count", "verified_audio_count", "missing_audio_count",
            "verified_audio_fraction", "git_commit",
        )}, ensure_ascii=False))
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
