"""Measure a local BM25 reference-atom baseline on the frozen retrieval split.

Candidate source atoms are provenance references, not human-labelled relevance
gold.  The output is therefore explicitly provisional and cannot enter the
runtime acceptance path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from ..history_rag import PreparedBM25
from ..history_rag_hybrid import evaluate_rankings

SCHEMA = "ayt-history-provisional-atom-bm25-baseline-v1"
SPLIT_SCHEMA = "ayt-history-candidate-split-v1"


def _atom_key(checksum: str, atom_id: str) -> str:
    return f"{checksum}:{atom_id}"


def build(candidate_pack: dict, split: dict, corpus: dict, *, limit: int = 3) -> dict:
    if candidate_pack.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("Özgün aday paketi gerekli")
    if split.get("schema") != SPLIT_SCHEMA or split.get("candidate_checksum") != candidate_pack.get("candidate_checksum"):
        raise ValueError("Aday paketiyle eşleşen dondurulmuş split gerekli")
    if corpus.get("schema") != "multi-history-rag-v1" or corpus.get("corpus_checksum") != candidate_pack.get("corpus_checksum"):
        raise ValueError("Aday paketiyle eşleşen çok kaynaklı atom corpus'u gerekli")
    if limit != 3:
        raise ValueError("Kilitli baseline yalnız top-3 ile ölçülür")
    split_rows = split.get("records", [])
    retrieval_ids = {row.get("id") for row in split_rows if row.get("split") == "retrieval_test"}
    if len(split_rows) != 120 or len(retrieval_ids) != 24:
        raise ValueError("Tam 120 satırlı ve 24 kayıtlı retrieval split gerekli")
    questions = {row.get("id"): row for row in candidate_pack.get("questions", [])}
    if set(questions) != {row.get("id") for row in split_rows}:
        raise ValueError("Split ve aday kimlikleri tam eşleşmeli")

    atoms_by_id: dict[str, dict] = {}
    duplicate_atom_count = 0
    for book in corpus.get("books", []):
        checksum = book.get("source_checksum")
        for atom in book.get("index", {}).get("evidence_atoms", []):
            if not checksum or not isinstance(atom.get("id"), str) or not isinstance(atom.get("text"), str):
                raise ValueError("Atom corpus'u kaynak kimliği, id ve metin taşımalı")
            row = {"id": _atom_key(checksum, atom["id"]), "page": atom.get("page", 0), "text": atom["text"]}
            previous = atoms_by_id.get(row["id"])
            if previous is not None:
                if previous != row:
                    raise ValueError("Aynı kaynak atom kimliği farklı içerikle yineleniyor")
                duplicate_atom_count += 1
                continue
            atoms_by_id[row["id"]] = row
    atoms = list(atoms_by_id.values())
    if not atoms:
        raise ValueError("Atom corpus'u boş")
    index = PreparedBM25(atoms)
    atom_ids = {row["id"] for row in atoms}
    rankings, latencies, references, cases = {}, [], [], []
    for question_id in sorted(retrieval_ids):
        question = questions[question_id]
        evidence = question.get("source_evidence", {})
        reference = _atom_key(str(evidence.get("source_checksum", "")), str(evidence.get("atom_id", "")))
        if reference not in atom_ids:
            raise ValueError("Adayın kaynak atomu corpus'ta yok")
        # Choices improve retrieval equivalently for every method but the
        # claimed label/explanation never enter the query or evaluation input.
        query = " ".join([question["question"], *question["choices"]])
        started = time.perf_counter()
        ranked = index.rank(query, limit=limit)
        latencies.append((time.perf_counter() - started) * 1000)
        rankings[question_id] = [row["id"] for row in ranked]
        references.append({"id": question_id, "gold_source_ids": [reference]})
        cases.append({"id": question_id, "reference_atom_id": reference,
                      "retrieved_atom_ids": rankings[question_id]})
    metrics = evaluate_rankings(references, rankings, latencies)
    return {
        "schema": SCHEMA,
        "candidate_checksum": candidate_pack["candidate_checksum"],
        "corpus_checksum": corpus["corpus_checksum"],
        "split_checksum": hashlib.sha256(
            json.dumps(split, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "method": "bm25_over_all_candidate_evidence_atoms",
        "k": limit,
        "corpus_atom_count": len(atoms),
        "exact_duplicate_atoms_deduplicated": duplicate_atom_count,
        "evaluated_split": "retrieval_test",
        "metrics": metrics,
        "cases": cases,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "reference_label_kind": "candidate_source_atom_unreviewed",
        "runtime_enabled": False,
        "qlora_enabled": False,
        "is_human_teacher_approval": False,
        "notice": "Provisional source-atom trace baseline only. Candidate atom references are not human relevance labels; unjudged results remain explicit and this output cannot select a runtime retriever.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.candidate_pack), load(args.split), load(args.corpus))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
