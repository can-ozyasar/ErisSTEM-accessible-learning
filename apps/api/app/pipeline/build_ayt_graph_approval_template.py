"""Build a private page/coordinate template for human AYT graph approval."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .promote_ayt_graph_approvals import build_template


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    output = build_template(corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"schema": output["schema"], "items": len(output["approvals"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
