"""Create a source-only review queue for writing original AYT History questions.

This tool never creates a student question, answer key, distractor, or coach
reply.  It stratifies checksum-bound MEB evidence atoms so the next review
step can decide whether a fact is suitable for an *original* text-only item.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict, deque
from pathlib import Path

from ..question_scope import visual_cue_in_text

SCHEMA = "ayt-history-original-authoring-queue-v1"
_VISUAL_ANCHOR = re.compile(r"\b(?:görsel|tablo|harita|grafik|şema|şekil)\s*\d", re.IGNORECASE)
_VISUAL_SUBJECT = re.compile(r"\b(?:heykel|fresk|resim|fotoğraf|karikatür|çizim|harita|tablo|grafik|şema)(?:[a-zçğıöşü']*)\b", re.IGNORECASE)
_VISUAL_LABEL = re.compile(r"\b(?:bilgi\s+)?görseli\s*\d", re.IGNORECASE)


def _eligible(book: dict, atom: dict) -> bool:
    quality = atom.get("quality", {})
    text = str(atom.get("text", "")).strip()
    return (
        bool(text)
        and not quality.get("warnings", [])
        and atom.get("pre_review", {}).get("decision") in {"manual_review", "review_for_approval"}
        and not visual_cue_in_text(text)
        and not _VISUAL_ANCHOR.search(text)
        and not _VISUAL_SUBJECT.search(text)
        and not _VISUAL_LABEL.search(text)
    )


def build(corpus: dict, *, limit: int = 120, source_offset: int = 0, card_start: int = 1) -> dict:
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("Checksum bağlı çoklu MEB corpus gerekli")
    if limit < 1 or limit > 120 or source_offset < 0 or card_start < 1:
        raise ValueError("Kuyruk limiti, kaynak ofseti veya kart başlangıcı geçersiz")
    by_section: dict[tuple[int, str], deque[dict]] = defaultdict(deque)
    source_bindings = []
    for book in sorted(corpus.get("books", []), key=lambda row: (row.get("grade", 0), row.get("source_checksum", ""))):
        if book.get("grade") not in {9, 10, 11, 12}:
            continue
        source_bindings.append({key: book[key] for key in ("grade", "source_name", "source_checksum")})
        sections = {row["id"]: row["title"] for row in book.get("index", {}).get("sections", [])}
        for atom in book.get("index", {}).get("evidence_atoms", []):
            if not _eligible(book, atom) or atom.get("section_id") not in sections:
                continue
            by_section[(book["grade"], atom["section_id"])].append({
                "grade": book["grade"], "section_id": atom["section_id"],
                "section_title": sections[atom["section_id"]], "source_id": book["source_name"],
                "source_checksum": book["source_checksum"], "page": atom["page"],
                "bbox": atom["bbox"], "atom_id": atom["id"], "quote": atom["text"],
            })
    if len(source_bindings) != 4:
        raise ValueError("9--12. sınıf için dört MEB kaynak bağlaması gerekli")
    sections = deque(sorted(by_section))
    cards = []
    target_count = source_offset + limit
    while sections and len(cards) < target_count:
        key = sections.popleft()
        candidates = by_section[key]
        if not candidates:
            continue
        atom = candidates.popleft()
        cards.append({
            "id": f"authoring-{len(cards) + 1:03d}", "status": "source_review_required",
            "authorship_required": "original", "visual_dependency": False,
            "question_text": None, "choices": None, "correct_label": None,
            "source_evidence": atom,
            "review_checks": ["fact_is_directly_supported", "text_only_question_possible",
                              "original_wording", "single_best_answer", "spoken_reading_ready"],
        })
        if candidates:
            sections.append(key)
    if len(cards) != target_count:
        raise ValueError("Yeterli görselsiz kaynak atomu bulunamadı")
    cards = cards[source_offset:]
    for index, card in enumerate(cards, start=card_start):
        card["id"] = f"authoring-{index:03d}"
    queue_checksum = hashlib.sha256(
        json.dumps(cards, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema": SCHEMA, "corpus_checksum": corpus["corpus_checksum"],
        "queue_checksum": queue_checksum,
        "source_bindings": source_bindings, "cards": cards,
        "summary": {"card_count": len(cards), "source_review_required": len(cards),
                    "source_offset": source_offset, "card_start": card_start},
        "answer_key_accessed": False, "worked_explanation_accessed": False,
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Source-only authoring queue. No card is an exam question or approved student evidence.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--source-offset", type=int, default=0)
    parser.add_argument("--card-start", type=int, default=1)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    result = build(corpus, limit=args.limit, source_offset=args.source_offset, card_start=args.card_start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
