"""Create an answer-free Qwen dense discovery input for reviewed AYT items."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ayt_target_atom_queue import _documents
from .prepare_atom_retrieval_audit import need_plan


def build(pool: dict, corpus: dict) -> dict:
    if pool.get("schema") not in {"ayt-target-discovery-pool-v1", "official-ayt-target-discovery-pool-v1"}:
        raise ValueError("Hedef soru keşif havuzu gerekli")
    if corpus.get("schema") != "multi-history-rag-v1" or pool.get("corpus_checksum") != corpus.get("corpus_checksum"):
        raise ValueError("Checksum bağlı hedef corpus gerekli")
    if pool.get("answer_key_accessed") is not False or pool.get("worked_explanation_accessed") is not False:
        raise ValueError("Cevap veya çözüm içeren soru havuzu kullanılamaz")
    target_ids = set(pool.get("candidate_section_ids", []))
    book = next((item for item in corpus.get("books", []) if item.get("source_role") == "primary_candidate"), None)
    if book is None:
        raise ValueError("Birincil 12. sınıf kaynak bulunamadı")
    atoms, contexts = _documents(book, target_ids)
    documents = [*atoms, *contexts]
    queries = []
    for row in pool.get("rows", []):
        if row.get("transcription_status") != "private_teacher_review_required":
            continue
        plan = need_plan(" ".join(row.get("target_section_options", [])), row["question"]["stem"])
        choices = [item["text"] for item in row["question"].get("choices", [])]
        queries.append({"id": row["candidate_id"], "query": " ".join([plan["retrieval_query"], *choices]),
                        "need_plan": plan, "evaluation_only": True})
    if not queries:
        raise ValueError("İncelenecek tam soru bulunamadı")
    return {
        "schema": "ayt-target-dense-discovery-v1", "corpus_checksum": corpus["corpus_checksum"],
        "source_binding": {"source_checksum": book["source_checksum"], "source_name": book["source_name"]},
        "documents": documents, "queries": queries, "target_section_ids": sorted(target_ids),
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Private answer-free candidate discovery. Dense ranks require separate PDF-crop review.",
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
