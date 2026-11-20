"""Build a blind, balanced PDF-review queue from private retrieval rankings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA_PAIRS = {
    ("ogm-ayt-discovery-calibration-v1", "ogm-ayt-relation-retrieval-rankings-v1"):
        "ogm-ayt-relation-discovery-review-queue-v1",
    ("ogm-ayt-atom-retrieval-audit-v1", "ogm-ayt-atom-retrieval-rankings-v1"):
        "ogm-ayt-atom-retrieval-review-queue-v1",
}
METHODS = ("bm25", "bge_dense", "bge_sparse", "rrf", "bge_dense_rerank")
QWEN_HYBRID_METHODS = ("bm25", "qwen_dense", "rrf", "rrf_rerank")
FORBIDDEN = {"answer", "answer_key", "answer_label", "correct_choice", "worked_explanation"}


def _balanced_ids(rankings: dict[str, list[str]], limit: int, methods: tuple[str, ...]) -> list[str]:
    """Round-robin top ranks so a lexical method cannot crowd out semantic ones."""
    chosen: list[str] = []
    maximum = max((len(rankings.get(method, [])) for method in methods), default=0)
    for position in range(maximum):
        for method in methods:
            candidates = rankings.get(method, [])
            if position < len(candidates) and candidates[position] not in chosen:
                chosen.append(candidates[position])
                if len(chosen) == limit:
                    return chosen
    return chosen


def _assert_safe_qwen_hybrid_contract(rankings: dict, documents: set[str], query_ids: set[str]) -> None:
    """Reject malformed or answer-bearing Qwen exports before crop review.

    The reranker is only meaningful when it reorders the declared RRF window.
    Enforcing that relation locally prevents a hand-edited Kaggle result from
    looking like an experiment outcome.
    """
    if tuple(rankings.get("ranking_methods", ())) != QWEN_HYBRID_METHODS:
        raise ValueError("Qwen hibrit yöntem sözleşmesi geçersiz")
    if rankings.get("runtime_enabled") is not False or rankings.get("qlora_enabled") is not False:
        raise ValueError("Kaggle retrieval çıktısı runtime veya QLoRA açamaz")
    if not isinstance(rankings.get("rerank_candidates"), int) or not 1 <= rankings["rerank_candidates"] <= 20:
        raise ValueError("Qwen reranker aday penceresi 1-20 arasında olmalı")
    if FORBIDDEN & set(rankings):
        raise ValueError("Kaggle retrieval çıktısı cevap alanı içeremez")
    if set(rankings.get("rankings", ())) != query_ids:
        raise ValueError("Kaggle ranking her kalibrasyon sorusunu tam bir kez içermeli")
    for query_id, methods in rankings["rankings"].items():
        if set(methods) != set(QWEN_HYBRID_METHODS):
            raise ValueError(f"Qwen ranking yöntemleri eksik: {query_id}")
        for method, item_ids in methods.items():
            if not isinstance(item_ids, list) or len(item_ids) != len(set(item_ids)):
                raise ValueError(f"Qwen ranking yinelenen veya geçersiz kimlik içeriyor: {query_id}/{method}")
            if not set(item_ids) <= documents:
                raise ValueError("Kaggle sonucu kalibrasyon corpus'u dışında kaynak içeriyor")
        window = methods["rrf"][:rankings["rerank_candidates"]]
        if not set(methods["rrf_rerank"]) <= set(window):
            raise ValueError("Reranker yalnız RRF aday penceresini yeniden sıralayabilir")


def build(calibration: dict, rankings: dict, corpus: dict, limit: int = 12) -> dict:
    methods = tuple(rankings.get("ranking_methods", METHODS))
    if not methods or len(methods) != len(set(methods)) or any(not isinstance(method, str) for method in methods):
        raise ValueError("Retrieval yöntem listesi geçersiz")
    if limit < len(methods):
        raise ValueError("Her retrieval yöntemi için dengeli inceleme alanı gerekli")
    queue_schema = SCHEMA_PAIRS.get((calibration.get("schema"), rankings.get("schema")))
    if queue_schema is None or corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Kalibrasyon, ranking ve corpus şemaları geçersiz")
    for key in ("source_checksum", "corpus_checksum"):
        if rankings.get(key) != calibration.get(key):
            raise ValueError("Kaggle ranking sürümü kalibrasyonla eşleşmiyor")
    if corpus.get("corpus_checksum") != calibration.get("corpus_checksum"):
        raise ValueError("MEB corpus sürümü kalibrasyonla eşleşmiyor")
    documents = {row["id"]: row for row in calibration.get("documents", [])}
    books = {book["source_checksum"]: book for book in corpus.get("books", [])}
    queue = []
    query_ids = {query["id"] for query in calibration.get("queries", [])}
    if methods == QWEN_HYBRID_METHODS:
        _assert_safe_qwen_hybrid_contract(rankings, set(documents), query_ids)
    if set(rankings.get("rankings", [])) != query_ids:
        raise ValueError("Kaggle ranking her kalibrasyon sorusunu tam bir kez içermeli")
    for query in calibration["queries"]:
        candidate_id = query["id"]
        ranked = rankings["rankings"][candidate_id]
        if any(method not in ranked for method in methods):
            raise ValueError("Her sorguda beklenen retrieval yöntemi gerekli")
        chosen = _balanced_ids(ranked, limit, methods)
        suggestions = []
        for item_id in chosen:
            document = documents.get(item_id)
            if document is None:
                raise ValueError("Kaggle sonucu kalibrasyon corpus'u dışında kaynak içeriyor")
            book = books.get(document["source_checksum"])
            if book is None:
                raise ValueError("Kaynak kitap corpus içinde bulunamadı")
            method_ranks = {method: values.index(item_id) + 1 for method, values in ranked.items()
                            if item_id in values}
            suggestions.append({
                "source_checksum": document["source_checksum"], "source_name": book["source_name"],
                "grade": document["grade"], "chunk_id": document["chunk_id"],
                "page": document["page"], "bbox": document["bbox"],
                "section_title": document["section_title"], "text": document["search_text"],
                "pre_review_decision": document["review_route"], "quality_warnings": [],
                "method_ranks": method_ranks, "review_status": "private_pdf_review_required",
            })
        queue.append({"candidate_id": candidate_id, "topic": query["topic"],
                      "status": "teacher_agent_source_review_required", "suggestions": suggestions})
    return {
        "schema": queue_schema, "source_checksum": calibration["source_checksum"],
        "corpus_checksum": calibration["corpus_checksum"], "proposals": queue,
        "ranking_methods": list(methods), "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Blind private PDF-review queue. Retrieval method ranks are audit metadata, never evidence approval.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    output = build(load(args.calibration), load(args.rankings), load(args.corpus), args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"question_count": len(output["proposals"]),
                      "card_count": sum(len(row["suggestions"]) for row in output["proposals"])}))


if __name__ == "__main__":
    main()
