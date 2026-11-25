"""Inventory exact V5 audio matches for a local exam without exporting content."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
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
        # The existing resolver indexes interface phrases by their text digest.
        # Question units have no exam-specific resolver or source binding yet.
        if row["kind"] == "interface":
            identifier = hashlib.sha256(row["spoken_text"].encode()).hexdigest()
            found = any(_resolve_at(root.resolve(), "interface", identifier, row["spoken_text"], None) is not None for root in roots)
            status = "verified_audio" if found else "missing_audio"
        else:
            status = "not_integrated"
        counts[(role, status)] += 1
    return {"schema": "ayt-static-audio-inventory-v1", "pack_sha256": hashlib.sha256(raw).hexdigest(),
            "voice_model_sha256": MODEL_SHA256, "question_count": manifest["summary"]["questions"],
            "summary": {role: {status: count for (kind, status), count in counts.items() if kind == role}
                        for role in sorted({kind for kind, _ in counts})},
            "digits_require_pronunciation_review": manifest["summary"]["units_with_digits_withheld"],
            "notice": "Question audio is not integrated into the exam path. Interface matches are exact verified installed WAVs."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--root", type=Path, action="append", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.pack, args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
