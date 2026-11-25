"""Prepare answer-blind source-text cards for provisional retrieval review.

The resulting queue is deliberately compatible with the generic relation
reviewer.  It contains a question, its choices and BM25's top-three source
atoms, but never an answer key, explanation or reference/gold atom.  AI labels
produced from it are research measurements only, not source approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

QUEUE_SCHEMA = "ogm-ayt-relation-discovery-review-queue-v1"
CALIBRATION_SCHEMA = "ayt-history-answer-blind-retrieval-calibration-v1"
BASELINE_SCHEMA = "ayt-history-provisional-atom-bm25-baseline-v1"
SPLIT_SCHEMA = "ayt-history-candidate-split-v1"


def _atom_key(checksum: str, atom_id: str) -> str:
    return f"{checksum}:{atom_id}"


def _atoms(corpus: dict) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for book in corpus.get("books", []):
        checksum = book.get("source_checksum")
        for atom in book.get("index", {}).get("evidence_atoms", []):
            atom_id, text = atom.get("id"), atom.get("text")
            if not isinstance(checksum, str) or not isinstance(atom_id, str) or not isinstance(text, str):
                raise TypeError("Atom corpus'u kaynak kimliği, id ve metin taşımalı")
            key = _atom_key(checksum, atom_id)
            card = {"source_checksum": checksum, "chunk_id": atom_id, "text": text}
            previous = rows.get(key)
            if previous is not None and previous != card:
                raise ValueError("Aynı kaynak atom kimliği farklı içerikle yineleniyor")
            rows[key] = card
    if not rows:
        raise ValueError("Atom corpus'u boş")
    return rows


def build(candidate_pack: dict, split: dict, corpus: dict, baseline: dict) -> tuple[dict, dict]:
    """Return ``(queue, calibration)`` for the frozen 24-question split."""
    if candidate_pack.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("Özgün aday paketi gerekli")
    if split.get("schema") != SPLIT_SCHEMA or split.get("candidate_checksum") != candidate_pack.get("candidate_checksum"):
        raise ValueError("Aday paketiyle eşleşen dondurulmuş split gerekli")
    if corpus.get("schema") != "multi-history-rag-v1" or corpus.get("corpus_checksum") != candidate_pack.get("corpus_checksum"):
        raise ValueError("Aday paketiyle eşleşen atom corpus'u gerekli")
    if baseline.get("schema") != BASELINE_SCHEMA:
        raise ValueError("Provisional BM25 baseline gerekli")
    for field, document in (("candidate_checksum", candidate_pack), ("corpus_checksum", corpus)):
        if baseline.get(field) != document.get(field):
            raise ValueError("BM25 baseline kaynak sürümüyle eşleşmiyor")
    if baseline.get("evaluated_split") != "retrieval_test" or baseline.get("k") != 3:
        raise ValueError("Yalnız dondurulmuş top-3 retrieval baseline kullanılabilir")

    split_ids = {row.get("id") for row in split.get("records", []) if row.get("split") == "retrieval_test"}
    if len(split.get("records", [])) != 120 or len(split_ids) != 24:
        raise ValueError("Tam 120 satırlı ve 24 kayıtlı retrieval split gerekli")
    questions = {row.get("id"): row for row in candidate_pack.get("questions", [])}
    cases = {row.get("id"): row for row in baseline.get("cases", [])}
    if set(questions) != {row.get("id") for row in split.get("records", [])} or set(cases) != split_ids:
        raise ValueError("Aday, split ve BM25 vaka kimlikleri tam eşleşmeli")

    cards = _atoms(corpus)
    proposals, queries = [], []
    for identifier in sorted(split_ids):
        question, case = questions[identifier], cases[identifier]
        retrieved = case.get("retrieved_atom_ids")
        if not isinstance(retrieved, list) or len(retrieved) != 3 or len(set(retrieved)) != 3:
            raise ValueError("Her BM25 vakası üç tekil aday atom taşımalı")
        try:
            suggestions = [cards[atom_id] for atom_id in retrieved]
        except KeyError as error:
            raise ValueError("BM25 aday atomu corpus'ta yok") from error
        question_text, choices = question.get("question"), question.get("choices")
        if not isinstance(question_text, str) or not isinstance(choices, list) or len(choices) != 5 or not all(isinstance(choice, str) for choice in choices):
            raise ValueError("Soru ve beş şık metni gerekli")
        # Keep answer-bearing fields out of both external-bound artifacts.
        queries.append({"id": identifier, "query": "\n".join([question_text, *[f"{letter}) {choice}" for letter, choice in zip("ABCDE", choices)]])})
        proposals.append({"candidate_id": identifier, "suggestions": suggestions})

    binding = {"candidate_checksum": candidate_pack["candidate_checksum"], "corpus_checksum": corpus["corpus_checksum"],
               "split_checksum": baseline.get("split_checksum"), "baseline_method": baseline.get("method"), "baseline_k": 3}
    queue = {"schema": QUEUE_SCHEMA, "source_checksum": candidate_pack["candidate_checksum"],
             "corpus_checksum": corpus["corpus_checksum"], "proposals": proposals,
             "binding": binding, "answer_key_accessed": False, "worked_explanation_accessed": False,
             "student_data_accessed": False, "runtime_enabled": False, "qlora_enabled": False,
             "is_human_teacher_approval": False,
             "notice": "Answer-blind source-text cards for provisional AI retrieval measurement only."}
    calibration = {"schema": CALIBRATION_SCHEMA, "source_checksum": candidate_pack["candidate_checksum"],
                   "corpus_checksum": corpus["corpus_checksum"], "queries": queries,
                   "binding": binding, "answer_key_accessed": False, "worked_explanation_accessed": False,
                   "student_data_accessed": False, "runtime_enabled": False, "qlora_enabled": False,
                   "is_human_teacher_approval": False,
                   "notice": "Answer-blind questions for provisional AI retrieval measurement only."}
    return queue, calibration


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--queue-output", type=Path, required=True)
    parser.add_argument("--calibration-output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    queue, calibration = build(load(args.candidate_pack), load(args.split), load(args.corpus), load(args.baseline))
    for path, payload in ((args.queue_output, queue), (args.calibration_output, calibration)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
