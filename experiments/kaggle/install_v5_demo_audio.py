"""Install downloaded private demo audio only after verifying every binding."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

MODEL_SHA = "8ec3a3312b9586a8650c38d2c8e8e8b6214851f13afbaa935ed4c9d598af8503"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def install(source_manifest: Path, generated: Path, destination: Path) -> int:
    if destination.exists():
        raise FileExistsError("destination_already_exists")
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    records = json.loads((generated / "run_records.json").read_text(encoding="utf-8"))
    if (source.get("schema_version") != "v5-demo-input-v1"
            or records.get("schema_version") != "v5-demo-audio-v1"
            or records.get("input_sha256") != digest(source_manifest)
            or records.get("model_sha256") != MODEL_SHA
            or records.get("pilot_limit") != 0):
        raise ValueError("input_or_model_mismatch")
    by_text = {}
    for row in records.get("records", []):
        text_hash = row.get("spoken_text_sha256", "")
        if row.get("status") != "generated" or len(text_hash) != 64 or any(c not in "0123456789abcdef" for c in text_hash) or text_hash in by_text:
            raise ValueError("invalid_or_duplicate_generated_asset")
        path = generated / "audio" / f"{text_hash}.wav"
        if not path.is_file() or path.stat().st_size != row.get("bytes") or digest(path) != row.get("audio_sha256"):
            raise ValueError("generated_audio_integrity_mismatch")
        with path.open("rb") as audio:
            header = audio.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise ValueError("invalid_wav")
        by_text[text_hash] = row
    items = []
    seen = set()
    for item in source.get("items", []):
        key = (item["kind"], item["id"])
        text_hash = item["spoken_text_sha256"]
        if key in seen or hashlib.sha256(item["spoken_text"].encode()).hexdigest() != text_hash:
            raise ValueError("invalid_source_item")
        seen.add(key)
        row = by_text.get(text_hash)
        if row is not None:
            items.append({"kind": key[0], "id": key[1], "spoken_text_sha256": text_hash,
                          "filename": f"audio/{text_hash}.wav", "bytes": row["bytes"], "audio_sha256": row["audio_sha256"]})
    if not items:
        raise ValueError("no_matching_assets")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".v5-demo-", dir=destination.parent) as temp:
        staging = Path(temp) / "package"
        (staging / "audio").mkdir(parents=True)
        for text_hash in {item["spoken_text_sha256"] for item in items}:
            shutil.copyfile(generated / "audio" / f"{text_hash}.wav", staging / "audio" / f"{text_hash}.wav")
            if digest(staging / "audio" / f"{text_hash}.wav") != by_text[text_hash]["audio_sha256"]:
                raise ValueError("installed_audio_integrity_mismatch")
        index = {"schema_version": "v5-demo-installed-v1", "model_sha256": MODEL_SHA,
                 "source_sha256": {"history": source["history_pdf_sha256"], "question": source["question_pdf_sha256"]},
                 "requires_listening_review": True, "items": items}
        (staging / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.rename(destination)
    return len(items)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(f"Installed {install(args.input, args.generated, args.destination)} source-bound demo units.")


if __name__ == "__main__":
    main()
