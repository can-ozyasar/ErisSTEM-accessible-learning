"""Create a content-free, question-group split before AYT evidence review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..tutor_dataset import split_question_ids

SCHEMA = "ogm-ayt-qlora-staging-split-v1"


def build(pool: dict) -> dict:
    if pool.get("schema") != "ogm-ayt-private-transcription-v1":
        raise ValueError("Private AYT OCR hazırlık havuzu gerekli")
    ids = [row.get("candidate_id") for row in pool.get("rows", [])]
    if len(ids) != 120 or any(not isinstance(item, str) for item in ids) or len(set(ids)) != 120:
        raise ValueError("Bölme için tam 120 benzersiz soru kimliği gerekli")
    splits = split_question_ids(ids)
    return {"schema": SCHEMA, "source_checksum": pool["source_checksum"], "question_count": 120,
            "splits": splits, "split_counts": {name: list(splits.values()).count(name)
                                                    for name in ("train", "dev", "sealed_test")},
            "answer_key_accessed": False, "source_approved_count": 0,
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Question-group split only. It contains no question text or source evidence and does not authorize training."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build(json.loads(args.pool.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["split_counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
