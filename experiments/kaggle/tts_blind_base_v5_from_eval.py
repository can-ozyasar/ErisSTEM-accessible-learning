"""Create a private blind listening bundle from verified V3/V5 evaluation audio."""

import hashlib
import json
import os
import random
import re
import shutil
from pathlib import Path

SOURCE = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-history-tts-finetune-eval-v1")
OUTPUT = Path("/kaggle/working/eristem-private-blind-base-v5")
EVAL = "eristem-tts-v3-finetune-eval-v5"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    if not os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        raise RuntimeError("private_kaggle_only")
    gold_paths = list(SOURCE.rglob("tts-history-eval-v1.json"))
    reports = [p for p in Path("/kaggle/input").rglob("run_records.json") if p.parent.name == EVAL]
    if len(gold_paths) != 1 or len(reports) != 1:
        raise RuntimeError("missing_or_ambiguous_inputs")
    gold = json.loads(gold_paths[0].read_text(encoding="utf-8"))
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    items = gold.get("items", [])
    if (gold.get("schema_version") != "tts-history-eval-v1" or len(items) != 14
            or report.get("schema_version") != "tts-v3-finetune-paired-eval-v5"
            or report.get("input_sha256") != digest(gold_paths[0])):
        raise RuntimeError("input_mismatch")
    rows = {}
    for row in report.get("records", []):
        candidate, item_id = row.get("candidate"), row.get("id")
        if candidate not in {"base", "grouped_v5"} or not isinstance(item_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", item_id) or row.get("status") != "generated":
            raise RuntimeError("invalid_record")
        key = (candidate, item_id)
        path = (reports[0].parent / row.get("audio_path", "")).resolve()
        if key in rows or not path.is_relative_to(reports[0].parent.resolve()) or path.name != f"{candidate}.{item_id}.wav" or not path.is_file() or digest(path) != row.get("audio_sha256"):
            raise RuntimeError("audio_integrity_failure")
        rows[key] = path
    if len(rows) != 28 or len({item.get("id") for item in items}) != 14:
        raise RuntimeError("incorrect_item_count")
    indices = list(range(14))
    random.Random(20261025).shuffle(indices)
    base_a = set(indices[:7])
    assignments = {}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for i, item in enumerate(items):
        pair = {"A": "base", "B": "grouped_v5"} if i in base_a else {"A": "grouped_v5", "B": "base"}
        assignments[str(i + 1)] = pair
        for label, candidate in pair.items():
            shutil.copyfile(rows[candidate, item["id"]], OUTPUT / f"{i + 1:02d}-{label}.wav")
    (OUTPUT / "private-blind-answer-key.json").write_text(json.dumps({"assignments": assignments}, indent=2), encoding="utf-8")
    print("14 kör ses çifti hazır. Lütfen cevap anahtarını açmayın.")


if __name__ == "__main__":
    main()
