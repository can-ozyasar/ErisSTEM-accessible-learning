"""Export a minimal, answer-free development set for dense retrieval evaluation.

The input intentionally includes no PDF, answer key, answer label, or worked
solution.  Relevance labels are coordinates selected during teacher-style PDF
crop review and are evaluation-only: they cannot approve a source or feed a
student prompt.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ayt_target_atom_queue import _documents
from .prepare_atom_retrieval_audit import need_plan

FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice", "worked_explanation", "pdf_path", "raw_pdf"}
SUPPORTED = {"direct", "bounded_inference"}


def build(pool: dict, corpus: dict, review: dict) -> dict:
    if pool.get("schema") != "ayt-target-discovery-pool-v1":
        raise ValueError("AYT hedef keşif havuzu gerekli")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Sürümlü corpus gerekli")
    if review.get("schema") != "teacher-target-atom-context-audit-local12-v1":
        raise ValueError("Yerel atom-bağlam öğretmen denetimi gerekli")
    if review.get("answer_key_accessed") or review.get("worked_explanation_accessed"):
        raise ValueError("Cevap anahtarı veya çözüm içeren denetim dışa aktarılamaz")
    binding = review.get("source_binding", {})
    if binding.get("source_checksum") != next((book.get("source_checksum") for book in corpus.get("books", [])
                                                if book.get("source_role") == "primary_candidate"), None):
        raise ValueError("İnceleme ve corpus kaynak sürümü eşleşmiyor")
    if FORBIDDEN & (set(pool) | set(corpus) | set(review)):
        raise ValueError("Yasaklı üst düzey alan bulundu")
    records = review.get("records", [])
    if not records or any(record.get("evaluation_only") is not True for record in records):
        raise ValueError("İnceleme kayıtları yalnız değerlendirme olarak işaretlenmeli")
    pool_rows = {row["candidate_id"]: row for row in pool.get("rows", [])}
    approved_for_eval = [record for record in records if record.get("assessment") in SUPPORTED]
    if len(approved_for_eval) < 8:
        raise ValueError("Yoğun retrieval deneyi için en az sekiz koordinatlı değerlendirme sorusu gerekli")
    if any(not record.get("gold_supporting_record_ids") for record in approved_for_eval):
        raise ValueError("Desteklenen her değerlendirme sorusunun koordinatlı altın kanıtı olmalı")
    book = next(book for book in corpus["books"] if book.get("source_role") == "primary_candidate")
    target_ids = set(pool["candidate_section_ids"])
    atoms, contexts = _documents(book, target_ids)
    documents = [*atoms, *contexts]
    known_ids = {document["record_id"] for document in documents}
    if any(set(record["gold_supporting_record_ids"]) - known_ids for record in approved_for_eval):
        raise ValueError("Altın kanıt hedef corpus dışında")
    queries = []
    for record in approved_for_eval:
        row = pool_rows.get(record["candidate_id"])
        if row is None or row.get("answer_key_accessed") is not False or row.get("worked_explanation_accessed") is not False:
            raise ValueError("Soru kaydı cevap/çözümden yalıtılmış olmalı")
        stem = row["question"]["stem"]
        plan = need_plan(row.get("topic", ""), stem)
        choices = [choice.get("text", "") for choice in row["question"].get("choices", [])]
        queries.append({
            "id": record["candidate_id"],
            "query": " ".join([plan["retrieval_query"], *choices]).strip(),
            "need_plan": plan,
            "gold_record_ids": sorted(record["gold_supporting_record_ids"]),
            "gold_label_origin": "teacher_pdf_crop_review",
            "evaluation_only": True,
        })
    return {
        "schema": "ayt-target-dense-retrieval-dev-v1",
        "corpus_checksum": corpus["corpus_checksum"],
        "source_binding": binding,
        "documents": documents,
        "queries": queries,
        "target_section_ids": sorted(target_ids),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Private development evaluation only. Gold crop IDs are not answers and cannot be used for runtime source approval.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.pool), load(args.corpus), load(args.review))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"queries": len(result["queries"]), "documents": len(result["documents"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
