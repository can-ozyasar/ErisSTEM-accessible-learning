"""Build an answer-free retrieval calibration set for a supplementary source."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice", "worked_explanation", "pdf_path", "raw_pdf"}


def build(corpus: dict, question_input: dict, reviews: list[dict]) -> dict:
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Sürümlü çok kaynaklı corpus gerekli")
    if question_input.get("schema") != "ogm-ayt-discovery-calibration-v1":
        raise ValueError("Yanıt içermeyen soru kalibrasyon girdisi gerekli")
    if FORBIDDEN & set(question_input):
        raise ValueError("Soru girdisi yasaklı alan içeriyor")
    query_by_id = {item["id"]: item for item in question_input["queries"]}
    target_ids = {
        review["candidate_id"]
        for review in reviews
        if review.get("reviewed")
        and review.get("question_diagnosis") == "candidate_set_insufficient"
    }
    queries = [query_by_id[candidate_id] for candidate_id in sorted(target_ids) if candidate_id in query_by_id]
    if len(queries) != len(target_ids):
        raise ValueError("İnceleme ile soru kalibrasyon kümesi eşleşmiyor")
    supplementary = [book for book in corpus["books"] if book.get("source_role") == "supplementary_candidate"]
    if len(supplementary) != 1:
        raise ValueError("Tam olarak bir inceleme amaçlı ek kaynak gerekli")
    book = supplementary[0]
    if book.get("student_runtime_eligible") or book.get("qlora_eligible"):
        raise ValueError("Ek kaynak onaysızken runtime veya QLoRA için açılamaz")
    documents = [{
        "id": f'{book["source_checksum"]}:{chunk["id"]}',
        "source_checksum": book["source_checksum"],
        "chunk_id": chunk["id"],
        "grade": book["grade"],
        "page": chunk["page"],
        "bbox": chunk["bbox"],
        "section_title": chunk["section_title"],
        "search_text": f'{chunk["section_title"]}\n{chunk["text"]}',
        "review_route": "supplementary_pdf_crop_required",
    } for chunk in book["index"]["chunks"]]
    return {
        "schema": "ogm-ayt-discovery-calibration-v1",
        "source_checksum": question_input["source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"],
        "selection": {"reason": "deep-window candidate_set_insufficient only", "query_count": len(queries)},
        "documents": documents,
        "queries": queries,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": ("Official supplementary-source coverage calibration only. Candidate rankings require "
                   "PDF-crop and teacher approval before runtime or QLoRA use."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--review", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review_records = []
    for path in args.review:
        review_records.extend(json.loads(path.read_text(encoding="utf-8"))["reviews"])
    result = build(
        json.loads(args.corpus.read_text(encoding="utf-8")),
        json.loads(args.questions.read_text(encoding="utf-8")),
        review_records,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"queries": len(result["queries"]), "documents": len(result["documents"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
