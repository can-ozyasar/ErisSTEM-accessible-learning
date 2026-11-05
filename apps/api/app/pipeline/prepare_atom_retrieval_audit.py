"""Prepare a fixed, answer-free audit for atom and context retrieval."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ..history_rag import terms

FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice", "worked_explanation", "pdf_path", "raw_pdf"}
QUESTION_WORDS = {"aşağıdakilerden", "aşağıdaki", "hangisi", "hangisidir", "verilen", "hangilerinden", "değildir", "olamaz"}
YEAR = re.compile(r"\b(?:MÖ|MS)?\s*\d{3,4}\b", re.IGNORECASE)
PROPER = re.compile(r"(?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){0,3})")


def need_plan(topic: str, stem: str) -> dict:
    content_terms = [word for word in terms(stem) if word not in QUESTION_WORDS]
    years = YEAR.findall(stem)
    entities = [value for value in PROPER.findall(stem) if len(terms(value))]
    relation = "fact"
    lowered = stem.casefold()
    if any(value in lowered for value in ("önce", "sonra", "sıra", "kronoloji")):
        relation = "chronology"
    elif any(value in lowered for value in ("neden", "sonuç", "etkisi", "amacıyla")):
        relation = "cause_effect"
    elif any(value in lowered for value in ("kim", "başkanı", "makam", "temsil")):
        relation = "person_or_institution"
    return {
        "topic": topic,
        "relation_intent": relation,
        "entity_hints": entities[:6],
        "time_hints": years[:4],
        "query_terms": content_terms[:32],
        "retrieval_query": " ".join([topic, *entities[:6], *years[:4], *content_terms[:32]]),
    }


def _reviews(paths: list[dict]) -> list[dict]:
    return [review for batch in paths for review in batch.get("reviews", [])]


def build(corpus: dict, questions: dict, failure_reviews: list[dict], comparator_reviews: list[dict]) -> dict:
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Sürümlü corpus gerekli")
    if questions.get("schema") != "ogm-ayt-private-transcription-v1":
        raise ValueError("Private soru transkripsiyonu gerekli")
    if FORBIDDEN & set(questions):
        raise ValueError("Soru kaynağı yasaklı alan içeriyor")
    supplementary = [book for book in corpus["books"] if book.get("source_role") == "supplementary_candidate"]
    if len(supplementary) != 1 or supplementary[0].get("student_runtime_eligible") or supplementary[0].get("qlora_eligible"):
        raise ValueError("Yalnız kapalı ek-kaynak adayı gerekli")
    index = supplementary[0]["index"]
    if index.get("schema") != 2 or not index.get("evidence_atoms") or not index.get("context_chunks"):
        raise ValueError("Atom ve bağlam indeksleri birlikte gerekli")
    failure_ids = {row["candidate_id"] for row in failure_reviews
                   if row.get("question_diagnosis") == "candidate_set_insufficient"}
    eligible_comparators = sorted({row["candidate_id"] for row in comparator_reviews
                                  if row.get("question_diagnosis") in {"direct_evidence_found", "multi_atom_required"}})
    comparator_ids = eligible_comparators[:20]
    if len(failure_ids) != 23 or len(comparator_ids) != 20:
        raise ValueError("Sabit 23 hata ve 20 karşılaştırma sorusu gerekli")
    questions_by_id = {row["candidate_id"]: row for row in questions["rows"]}
    selected_ids = sorted(failure_ids | set(comparator_ids))
    if any(candidate_id not in questions_by_id for candidate_id in selected_ids):
        raise ValueError("Seçili soru transkripsiyonu bulunamadı")
    selected_questions = [questions_by_id[candidate_id] for candidate_id in selected_ids]
    if any(row.get("answer_key_accessed") is not False or row.get("worked_explanation_accessed") is not False
           or row.get("transcription_status") != "private_teacher_review_required" for row in selected_questions):
        raise ValueError("Audit soruları cevap anahtarı ve çözümden yalıtılmış özel transkripsiyon olmalı")
    source_checksum = supplementary[0]["source_checksum"]
    documents = []
    for granularity, records in (("atom", index["evidence_atoms"]), ("context", index["context_chunks"])):
        for record in records:
            title = record.get("heading") or record["section_title"]
            documents.append({
                "id": f'{source_checksum}:{granularity}:{record["id"]}',
                "source_checksum": source_checksum, "chunk_id": record["id"], "granularity": granularity,
                "grade": supplementary[0]["grade"], "page": record["page"], "bbox": record["bbox"],
                "section_title": record["section_title"], "heading": record.get("heading"),
                "search_text": f'{record["section_title"]}\n{title}\n{record["text"]}',
                "review_route": "supplementary_pdf_crop_required",
            })
    queries = []
    for candidate_id, row in zip(selected_ids, selected_questions):
        stem = row["question"]["stem"]
        plan = need_plan(row["topic"], stem)
        queries.append({"id": candidate_id, "topic": row["topic"], "query": plan["retrieval_query"],
                        "need_plan": plan, "audit_group": "prior_failure" if candidate_id in failure_ids else "prior_success"})
    return {
        "schema": "ogm-ayt-atom-retrieval-audit-v1", "source_checksum": questions["source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"], "documents": documents, "queries": queries,
        "selection": {"prior_failure_count": len(failure_ids), "prior_success_count": len(comparator_ids)},
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Answer-free private audit. Gold labels remain in a separate evaluation-only store.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--failure-review", type=Path, action="append", required=True)
    parser.add_argument("--comparator-review", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.corpus), load(args.questions), _reviews([load(path) for path in args.failure_review]),
                   _reviews([load(path) for path in args.comparator_review]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"queries": len(result["queries"]), "documents": len(result["documents"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
