"""Project one validated Qwen challenger method into blind PDF-review cases."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ALLOWED_METHODS = {"bm25", "qwen_dense", "rrf"}


def _checksum(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def build(candidate: dict[str, Any], split: dict[str, Any], ranking: dict[str, Any], method: str) -> dict[str, Any]:
    if method not in ALLOWED_METHODS:
        raise ValueError("Yalnız BM25, Qwen dense veya RRF adayları PDF incelemesine hazırlanabilir")
    if candidate.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("Özgün aday paketi gerekli")
    if split.get("schema") != "ayt-history-candidate-split-v1":
        raise ValueError("Dondurulmuş bölümleme gerekli")
    if ranking.get("schema") != "ogm-ayt-relation-retrieval-rankings-v1":
        raise ValueError("Doğrulanmış Qwen sıralama çıktısı gerekli")
    if (ranking.get("source_checksum") != candidate.get("candidate_checksum")
            or ranking.get("corpus_checksum") != candidate.get("corpus_checksum")
            or ranking.get("ranking_methods") != ["bm25", "qwen_dense", "rrf"]):
        raise ValueError("Qwen çıktısı güncel aday paketi ve corpus ile eşleşmeli")
    retrieval_ids = {row.get("id") for row in split.get("records", []) if row.get("split") == "retrieval_test"}
    rankings = ranking.get("rankings")
    if len(retrieval_ids) != 24 or not isinstance(rankings, dict) or set(rankings) != retrieval_ids:
        raise ValueError("Tam dondurulmuş 24 retrieval vakası gerekli")
    cases = []
    for identifier in sorted(retrieval_ids):
        atom_ids = rankings[identifier].get(method)
        if not isinstance(atom_ids, list) or len(atom_ids) < 3 or len(set(atom_ids[:3])) != 3:
            raise ValueError("Her Qwen vakası en az üç tekil aday taşımalı")
        cases.append({"id": identifier, "retrieved_atom_ids": atom_ids[:3]})
    return {
        "schema": "ayt-history-provisional-atom-bm25-baseline-v1",
        "candidate_checksum": candidate["candidate_checksum"],
        "corpus_checksum": candidate["corpus_checksum"],
        "split_checksum": _checksum(split), "k": 3, "cases": cases,
        "challenger_method": method, "rankings_checksum": _checksum(ranking),
        "answer_key_accessed": False, "student_data_accessed": False,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Compatibility projection for rank-blind PDF review only; this is not BM25 evidence or a runtime artifact.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--ranking", type=Path, required=True)
    parser.add_argument("--method", choices=sorted(ALLOWED_METHODS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(read(args.candidate_pack), read(args.split), read(args.ranking), args.method)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
