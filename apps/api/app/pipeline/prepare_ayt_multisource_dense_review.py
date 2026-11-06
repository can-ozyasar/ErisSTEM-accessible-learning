"""Prepare a checksum-bound PDF-crop review queue for multi-book AYT retrieval.

Ranks are candidate leads only.  The resulting queue is private and retains the
source checksum on every card so an auditor must inspect the matching PDF,
rather than accidentally treating a crop from another grade as evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "official-ayt-multisource-dense-review-queue-v1"


def _assert_false(payload: dict) -> None:
    for key in (
        "answer_key_accessed",
        "worked_explanation_accessed",
        "runtime_enabled",
        "qlora_enabled",
    ):
        if payload.get(key) is not False:
            raise ValueError(f"{key} false olmalı")


def _crop_key(document: dict) -> tuple[str, int, tuple[float, ...]]:
    return (
        document["source_checksum"],
        int(document["page"]),
        tuple(round(float(value), 2) for value in document["bbox"]),
    )


def _validate_inputs(discovery: dict, rankings: dict) -> None:
    if discovery.get("schema") != "ayt-multisource-dense-discovery-v1":
        raise ValueError("Çok kaynaklı yoğun keşif girdisi gerekli")
    if rankings.get("schema") != "official-ayt-multisource-dense-discovery-rankings-v1":
        raise ValueError("Çok kaynaklı yoğun sıralama çıktısı gerekli")
    _assert_false(discovery)
    _assert_false(rankings)
    if rankings.get("corpus_checksum") != discovery.get("corpus_checksum"):
        raise ValueError("Sıralama ve keşif corpus checksum değerleri eşleşmiyor")
    if rankings.get("source_bindings") != discovery.get("source_bindings"):
        raise ValueError("Sıralama ve keşif kaynak bağları eşleşmiyor")


def _ranked_cards(documents: dict[str, dict], ranks: dict[str, list[str]], limit: int) -> list[dict]:
    by_crop: dict[tuple[str, int, tuple[float, ...]], dict] = {}
    for method in ("qwen_dense_tr", "bm25", "rrf"):
        for position, document_id in enumerate(ranks.get(method, [])[:limit], start=1):
            document = documents.get(document_id)
            if document is None:
                raise ValueError("Sıralama keşif dışındaki bir belgeyi içeriyor")
            row = by_crop.setdefault(_crop_key(document), {**document, "retrieval_method_ranks": {}})
            row["retrieval_method_ranks"][method] = position
    return list(by_crop.values())


def _diverse(cards: list[dict], limit: int) -> list[dict]:
    def key(card: dict) -> tuple[int, int, int, str]:
        ranks = card["retrieval_method_ranks"]
        return (min(ranks.values()), sum(ranks.values()), card["page"], card["record_id"])

    result: list[dict] = []
    seen_pages: set[tuple[str, int]] = set()
    for card in sorted(cards, key=key):
        page = (card["source_checksum"], card["page"])
        if page in seen_pages:
            continue
        result.append(card)
        seen_pages.add(page)
        if len(result) == limit:
            return result
    chosen = {_crop_key(card) for card in result}
    for card in sorted(cards, key=key):
        if _crop_key(card) in chosen:
            continue
        result.append(card)
        chosen.add(_crop_key(card))
        if len(result) == limit:
            break
    return result


def build(discovery: dict, rankings: dict, *, first_stage_limit: int = 20, review_limit: int = 10) -> dict:
    _validate_inputs(discovery, rankings)
    if first_stage_limit < 3 or review_limit < 3 or review_limit > first_stage_limit:
        raise ValueError("Aday ve inceleme sınırları geçersiz")
    documents = {document["id"]: document for document in discovery.get("documents", [])}
    queries = {query["id"]: query for query in discovery.get("queries", [])}
    if set(queries) != set(rankings.get("rankings", {})):
        raise ValueError("Her kapalı değerlendirme sorusu tam bir sıralama içermeli")

    rows = []
    for candidate_id, query in queries.items():
        selected = _diverse(
            _ranked_cards(documents, rankings["rankings"][candidate_id], first_stage_limit), review_limit
        )
        rows.append(
            {
                "candidate_id": candidate_id,
                "need_plan": query["need_plan"],
                "first_stage_limit": first_stage_limit,
                "suggestions": [
                    {
                        "source_key": f"{card['source_checksum']}:{card['record_id']}",
                        "record_id": card["record_id"],
                        "granularity": card["granularity"],
                        "source_checksum": card["source_checksum"],
                        "source_name": card["source_name"],
                        "section_id": card["section_id"],
                        "section_title": card["section_title"],
                        "heading": card.get("heading"),
                        "page": card["page"],
                        "bbox": card["bbox"],
                        "excerpt": card["excerpt"],
                        "retrieval_method_ranks": card["retrieval_method_ranks"],
                        "review_status": "private_pdf_crop_review_required",
                    }
                    for card in selected
                ],
            }
        )
    return {
        "schema": SCHEMA,
        "corpus_checksum": discovery["corpus_checksum"],
        "source_bindings": discovery["source_bindings"],
        "embedding_model": rankings.get("embedding_model"),
        "retrieval": {
            "dense_method": "qwen_dense_tr",
            "lexical_method": "bm25",
            "fusion_method": "rrf",
            "first_stage_limit": first_stage_limit,
            "review_limit": review_limit,
            "deduplication": "exact_pdf_crop",
            "diversity": "one_per_source_page_before_extra_crops",
        },
        "rows": rows,
        "reviewer_kind_required": "history_teacher_agent_v1",
        "is_human_teacher_approval": False,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Ranking is a private discovery lead only. Every card must be checked against the PDF identified by its source checksum before graph, student RAG, or QLoRA use.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first-stage-limit", type=int, default=20)
    parser.add_argument("--review-limit", type=int, default=10)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.discovery), load(args.rankings), first_stage_limit=args.first_stage_limit, review_limit=args.review_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"questions": len(result["rows"]), "cards": sum(len(row["suggestions"]) for row in result["rows"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
