"""Create a content-free architecture snapshot from a private multi-book corpus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..knowledge_architecture import build_pilot_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    result = build_pilot_snapshot(corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
