"""DB'deki private Gold anotasyonlarını Kaggle'a aktarılabilir manifestte birleştirir."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from ..job_store import BenchmarkAnnotation, make_session_factory


def main() -> int:
    parser = argparse.ArgumentParser(description="Private Gold anotasyonlarını dışa aktarır")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    sessions = make_session_factory()
    with sessions() as session:
        annotations = {
            item.id: item.expected for item in session.scalars(select(BenchmarkAnnotation))
        }
    manifest["items"] = [
        {**item, "expected": annotations.get(item["id"], item.get("expected", ""))}
        for item in manifest["items"]
    ]
    manifest["annotation_state"] = (
        "ready" if all(item["expected"] for item in manifest["items"]) else "incomplete"
    )
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
