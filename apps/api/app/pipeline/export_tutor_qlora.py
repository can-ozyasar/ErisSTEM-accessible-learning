"""Export reviewed coach behaviour for private Kaggle QLoRA input.

The Kaggle directory receives train/dev protocol examples only. Sealed test
examples remain in a separate local directory and are never copied there.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ..job_store import make_session_factory
from ..learning_operations import LearningOperationsStore
from ..tutor_dataset import export_rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///eristem-dev.db"))
    parser.add_argument("--kaggle-output", type=Path, required=True)
    parser.add_argument("--sealed-output", type=Path, required=True)
    parser.add_argument("--module-id", required=True, help="Question-bank source checksum's first 16 characters")
    args = parser.parse_args()
    store = LearningOperationsStore(make_session_factory(args.database_url))
    rows, summary = export_rows(store.list("tutor_review", args.module_id))
    for split in ("train", "dev"):
        write_jsonl(args.kaggle_output / f"{split}.jsonl", rows[split])
    write_jsonl(args.sealed_output / "sealed_test.jsonl", rows["sealed_test"])
    (args.kaggle_output / "manifest.json").write_text(json.dumps({**summary, "sealed_test_included": False},
                                                               ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**summary, "kaggle_output": str(args.kaggle_output), "sealed_output": str(args.sealed_output)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
