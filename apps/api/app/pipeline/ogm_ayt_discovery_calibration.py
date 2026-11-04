"""Export a private, answer-free calibration set for semantic AYT evidence retrieval.

The set deliberately starts from questions where the narrow lexical review did
not find a direct source.  It lets us measure whether wider semantic retrieval
and document context solve a retrieval problem before changing the product.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from .ogm_ayt_retrieval_gold import SCHEMA

OUTPUT_SCHEMA = "ogm-ayt-discovery-calibration-v1"
FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice", "worked_explanation"}


def _question_text(row: dict) -> str:
    question = row.get("question", {})
    choices = question.get("choices", [])
    return " ".join(part.strip() for part in [question.get("stem", ""),
                                              *(choice.get("text", "") for choice in choices)]
                    if part and part.strip())


def _eligible_documents(corpus: dict) -> list[dict]:
    documents = []
    for book in corpus.get("books", []):
        for chunk in book.get("index", {}).get("chunks", []):
            if chunk.get("pre_review", {}).get("decision") == "do_not_use":
                continue
            documents.append({
                "id": f'{book["source_checksum"]}:{chunk["id"]}',
                "source_checksum": book["source_checksum"], "chunk_id": chunk["id"],
                "grade": book.get("grade"), "page": chunk.get("page"),
                "bbox": chunk.get("bbox"), "section_title": chunk.get("section_title", ""),
                # Heading augments retrieval but cannot itself act as evidence.
                "search_text": f'{chunk.get("section_title", "")}\n{chunk.get("text", "")}'.strip(),
                "review_route": ("priority" if chunk.get("pre_review", {}).get("decision") == "review_for_approval"
                                 else "context_check_required"),
            })
    return sorted(documents, key=lambda item: item["id"])


def build(transcriptions: dict, baseline_gold: dict, corpus: dict, split: dict, per_topic: int = 4) -> dict:
    if per_topic < 1:
        raise ValueError("Ünite başına örnek sayısı pozitif olmalı")
    if (transcriptions.get("schema") != "ogm-ayt-private-transcription-v1"
            or baseline_gold.get("schema") != SCHEMA
            or corpus.get("schema") != "multi-history-rag-v1"
            or split.get("schema") != "ogm-ayt-qlora-staging-split-v1"):
        raise ValueError("Sürümlü transkripsiyon, Gold, split ve MEB corpus gerekli")
    if (transcriptions.get("source_checksum") != baseline_gold.get("source_checksum")
            or baseline_gold.get("corpus_checksum") != corpus.get("corpus_checksum")):
        raise ValueError("Soru ve kaynak sürümleri eşleşmiyor")
    if FORBIDDEN & set(transcriptions):
        raise ValueError("Kalibrasyon girdisinde cevap anahtarı bulunamaz")
    cases = baseline_gold.get("cases", [])
    if any(not case.get("reviewed") or not case.get("coverage_complete")
           or not isinstance(case.get("abstain"), bool) for case in cases):
        raise ValueError("Yalnız tam incelenmiş Gold çekimserlikleri kullanılabilir")
    abstained = {case["candidate_id"] for case in cases if case["abstain"]}
    split_by_id = split.get("splits", {})
    if not split_by_id or not abstained <= set(split_by_id):
        raise ValueError("Kalibrasyon soruları için sürümlü split kaydı gerekli")
    by_topic: dict[str, list[dict]] = defaultdict(list)
    for row in transcriptions.get("rows", []):
        if (row.get("candidate_id") in abstained
                and split_by_id.get(row["candidate_id"]) in {"train", "dev"}
                and row.get("transcription_status") == "private_teacher_review_required"):
            by_topic[row.get("topic", "Başlıksız")].append(row)
    selected = []
    for topic in sorted(by_topic):
        selected.extend(sorted(by_topic[topic], key=lambda row: row["candidate_id"])[:per_topic])
    if not selected:
        raise ValueError("Kalibrasyon için çekimser ve okunabilir soru yok")
    queries = [{"id": row["candidate_id"], "topic": row.get("topic"),
                "query": _question_text(row), "question_source": "private_transcription"}
               for row in selected]
    if any(FORBIDDEN & set(query) for query in queries):
        raise ValueError("Kalibrasyon sorgusunda yasaklı cevap alanı bulundu")
    return {
        "schema": OUTPUT_SCHEMA,
        "source_checksum": baseline_gold["source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"],
        "selection": {"baseline": "reviewed_abstentions", "allowed_splits": ["train", "dev"], "per_topic": per_topic,
                      "topic_count": len(by_topic), "query_count": len(queries)},
        "documents": _eligible_documents(corpus), "queries": queries,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": ("Private calibration export. It contains no answer keys or worked explanations. "
                   "Documents are retrieval candidates only and need PDF-crop review before approval."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--baseline-gold", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-topic", type=int, default=4)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    output = build(load(args.transcriptions), load(args.baseline_gold), load(args.corpus), load(args.split), args.per_topic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"query_count": len(output["queries"]), "document_count": len(output["documents"])}))


if __name__ == "__main__":
    main()
