"""Build a checksum-bound AYT graph from a promoted private corpus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..ayt_knowledge_graph import KnowledgeGraphBuilder


def build(corpus: dict) -> dict:
    graph = KnowledgeGraphBuilder(corpus["corpus_checksum"]).add_corpus(corpus).build()
    return graph.model_dump(mode="json", by_alias=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    payload = build(corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    approved = sum(bool(node.get("approved")) for node in payload["nodes"])
    print(json.dumps({"schema": payload["schema"], "nodes": len(payload["nodes"]),
                      "edges": len(payload["edges"]), "approved_nodes": approved}, ensure_ascii=False))


if __name__ == "__main__":
    main()
