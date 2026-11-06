"""Prepare an answer-free AYT coverage experiment over all local MEB sources.

This is a diagnostic corpus only.  It deliberately keeps 10th/11th/12th grade
books and the AYT summary bound to their own checksums; no source is approved
for student RAG or QLoRA by this preparation step.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ayt_target_atom_queue import _documents
from .prepare_atom_retrieval_audit import need_plan

SCHEMA = "ayt-full-multisource-dense-discovery-v1"


def build(query_discovery: dict, corpus: dict) -> dict:
    if query_discovery.get("schema") != "ayt-multisource-dense-discovery-v1":
        raise ValueError("Mevcut cevap-anahtarsız AYT ihtiyaç keşfi gerekli")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Sürümlü çok kaynaklı MEB corpus gerekli")
    for payload in (query_discovery, corpus):
        for key in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"):
            if payload.get(key) is True:
                raise ValueError(f"{key} erişimli corpus kullanılamaz")
    documents: list[dict] = []
    bindings: list[dict] = []
    for book in corpus.get("books", []):
        sections = {section.get("section_id", section.get("id")) for section in book.get("index", {}).get("sections", [])}
        atoms, contexts = _documents(book, sections)
        documents.extend(atoms)
        documents.extend(contexts)
        bindings.append({
            "source_checksum": book["source_checksum"],
            "source_name": book["source_name"],
            "grade": book["grade"],
            "source_role": book.get("source_role", "textbook_candidate"),
        })
    if not documents or len(bindings) < 3:
        raise ValueError("En az üç temiz MEB kaynağı gerekli")
    queries = []
    for query in query_discovery.get("queries", []):
        plan = query.get("need_plan") or need_plan(query.get("query", ""), query.get("query", ""))
        queries.append({
            "id": query["id"],
            "query": plan["retrieval_query"],
            "need_plan": plan,
            "evaluation_only": True,
        })
    return {
        "schema": SCHEMA,
        "corpus_checksum": corpus["corpus_checksum"],
        "source_bindings": bindings,
        "documents": documents,
        "queries": queries,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Private full-source coverage experiment. Ranking is candidate discovery only; every card requires checksum-bound PDF crop review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.queries), load(args.corpus))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"documents": len(result["documents"]), "queries": len(result["queries"]), "sources": len(result["source_bindings"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
