"""Build answer-free root and option queries for relation-aware evidence discovery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ayt_target_atom_queue import _documents
from .prepare_atom_retrieval_audit import need_plan


def build(pool: dict, corpus: dict) -> dict:
    if pool.get("schema") != "official-ayt-target-discovery-pool-v1":
        raise ValueError("Resmî AYT hedef soru havuzu gerekli")
    if corpus.get("schema") != "multi-history-rag-v1" or pool.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("Checksum bağlı corpus gerekli")
    if pool.get("answer_key_accessed") is not False or pool.get("worked_explanation_accessed") is not False:
        raise ValueError("Cevap/çözüm yalıtımı zorunlu")
    source = next((book for book in corpus["books"] if book.get("source_role") == "primary_candidate"), None)
    if source is None:
        raise ValueError("Birincil yerel 12. sınıf kaynak bulunamadı")
    target_ids = set(pool["candidate_section_ids"])
    atoms, contexts = _documents(source, target_ids)
    rows = []
    for item in pool["rows"]:
        stem = item["question"]["stem"]
        plan = need_plan(" ".join(item.get("target_section_options", [])), stem)
        subqueries = [{"kind": "question_root", "text": plan["retrieval_query"]}]
        for choice in item["question"].get("choices", []):
            # A choice is a hypothesis to test, never a hidden answer label.
            subqueries.append({"kind": "choice_hypothesis", "label": choice["label"],
                               "text": f"{plan['retrieval_query']} {choice['text']}"})
        rows.append({"id": item["candidate_id"], "need_plan": plan, "subqueries": subqueries, "evaluation_only": True})
    return {
        "schema": "official-ayt-target-multiquery-discovery-v1", "corpus_checksum": corpus["corpus_checksum"],
        "source_binding": {"source_checksum": source["source_checksum"], "source_name": source["source_name"]},
        "documents": [*atoms, *contexts], "queries": rows, "target_section_ids": sorted(target_ids),
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Choice texts are answer-free hypotheses for contrast retrieval only; all output requires teacher-agent crop review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.pool), load(args.corpus))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"queries": len(result["queries"]), "documents": len(result["documents"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
