"""Create a root-only dense-retrieval ablation for official AYT questions."""
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
        raise ValueError("Cevap veya çözüm erişimli havuz kullanılamaz")
    source = next((book for book in corpus["books"] if book.get("source_role") == "primary_candidate"), None)
    if source is None:
        raise ValueError("Birincil yerel 12. sınıf kaynak bulunamadı")
    atoms, contexts = _documents(source, set(pool["candidate_section_ids"]))
    queries = []
    for row in pool["rows"]:
        if row.get("transcription_status") != "private_teacher_review_required":
            continue
        plan = need_plan(" ".join(row.get("target_section_options", [])), row["question"]["stem"])
        queries.append({"id": row["candidate_id"], "query": plan["retrieval_query"], "need_plan": plan, "evaluation_only": True})
    if not queries:
        raise ValueError("İncelenecek tam soru bulunamadı")
    return {
        "schema": "ayt-target-root-dense-discovery-v1",
        "corpus_checksum": corpus["corpus_checksum"],
        "source_binding": {"source_checksum": source["source_checksum"], "source_name": source["source_name"]},
        "documents": [*atoms, *contexts],
        "queries": queries,
        "target_section_ids": sorted(pool["candidate_section_ids"]),
        "query_policy": "question_root_and_need_plan_only",
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Answer-free root-only ablation. Choice texts are excluded from retrieval; every result requires separate PDF-crop review.",
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
