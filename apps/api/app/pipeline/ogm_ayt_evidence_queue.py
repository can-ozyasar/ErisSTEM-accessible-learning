"""Build a private MEB-evidence review queue for transcribed OGM AYT items."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from ..history_rag import PreparedBM25, terms

SCHEMA = "ogm-ayt-evidence-review-queue-v3"
TRANSCRIPTION_SCHEMAS = {"ogm-ayt-private-transcription-v1", "ayt-target-discovery-pool-v1"}
# These words occur in a question form far more often than they identify a
# historical claim.  They are excluded only from the *literal claim coverage*
# check below.  BM25 continues to see the complete question and choices.
QUESTION_FORM_TERMS = {
    "aşağıdakilerden",
    "aşağıdaki",
    "hangisi",
    "hangilerinden",
    "hangileri",
    "hangisidir",
    "verilen",
    "verilmiştir",
    "göre",
    "olarak",
    "ilgili",
    "değildir",
    "olamaz",
    "ulaşılabilir",
    "söylenebilir",
    "çıkarılabilir",
    "doğru",
    "yanlış",
    "bilgi",
    "ifadeler",
    "ifade",
    "yargı",
    "yargılardan",
    "özellik",
    "özelliklerden",
    "olduğu",
    "olması",
    "amaçlanmıştır",
}
GENERIC_CLAIM_TERMS = {
    "türkiye",
    "dünya",
    "dönem",
    "devlet",
    "savaş",
    "milli",
    "mücadele",
    "tarih",
    "tarihi",
    "gelişme",
    "olay",
    "bilgi",
    "toplum",
    "ülke",
}
CAPITALISED_TOKEN = re.compile(r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+|MÖ|MS|\d{3,4}")
TOPIC_SECTION_HINTS = {
    "I. Dünya Savaşı Sürecinde Osmanlı Devleti": (
        "I. DÜNYA SAVAŞI SÜRECİNDE OSMANLI DEVLETİ", "I. DÜNYA SAVAŞI", "OSMANLI DEVLETİ",
    ),
    "Millî Mücadele’ye Hazırlık Dönemi": (
        "MİLLÎ MÜCADELE’YE HAZIRLIK", "MİLLİ MÜCADELEYE HAZIRLIK", "HAZIRLIK DÖNEMİ",
    ),
    "Batı Cephesi ve Bu Cephede Öne Çıkan Şahsiyetler": (
        "BATI CEPHESİ", "BATI CEPHESİNDE",
    ),
    "Doğu ve Güney Cepheleri ile Bu Cephelerde Öne Çıkan Şahsiyetler": (
        "DOĞU VE GÜNEY CEPHELERİ", "DOĞU CEPHESİ", "GÜNEY CEPHESİ",
    ),
    "Atatürk İlkeleri": ("ATATÜRK İLKELERİ",),
    "Siyasi Alandaki Gelişmeler": ("SİYASİ ALANDAKİ GELİŞMELER",),
    "Millî Mücadele": ("MİLLÎ MÜCADELE", "BÜYÜK MİLLET MECLİSİ", "SEVR", "CEPHELER", "LOZAN"),
    "Atatürkçülük ve Türk İnkılabı": (
        "ATATÜRK İLKELERİ",
        "İNKILAP",
        "ATATÜRK DÖNEMİ",
        "ATATÜRKÇÜ DÜŞÜNCE",
    ),
    "İki Savaş Arasındaki Dönemde Türkiye ve Dünya": ("İKİ DÜNYA SAVAŞI ARASINDAKİ",),
    "II. Dünya Savaşı Sürecinde Türkiye ve Dünya": ("II. DÜNYA SAVAŞI",),
    "II. Dünya Savaşı Sonrasında Türkiye ve Dünya": (
        "II. DÜNYA SAVAŞI SONRASI",
        "1950’LERDE TÜRKİYE",
    ),
    "21. Yüzyılın Eşiğinde Türkiye ve Dünya": ("1960 SONRASI", "1990 SONRASI"),
}


def _normalise(value: str) -> str:
    return " ".join(value.replace("İ", "I").replace("ı", "i").upper().split())


def _topic_pool(pool: list[tuple[dict, dict]], topic: str) -> list[tuple[dict, dict]]:
    hints = TOPIC_SECTION_HINTS.get(topic)
    if not hints:
        return []
    normalized_hints = tuple(_normalise(hint) for hint in hints)
    return [
        (book, chunk)
        for book, chunk in pool
        if any(hint in _normalise(chunk.get("section_title", "")) for hint in normalized_hints)
    ]


def _eligible(corpus: dict) -> list[tuple[dict, dict]]:
    rows = []
    for book in corpus.get("books", []):
        if book.get("grade") not in {10, 11, 12}:
            continue
        for chunk in book["index"].get("chunks", []):
            if chunk.get("pre_review", {}).get(
                "decision"
            ) == "review_for_approval" and not chunk.get("quality", {}).get("warnings"):
                rows.append((book, chunk))
    return rows


def _query(row: dict) -> str:
    return " ".join(
        [row["question"]["stem"], *(choice["text"] for choice in row["question"]["choices"])]
    )


def _claim_terms(row: dict) -> set[str]:
    """Return inspectable question-root terms without using an answer key.

    Choices are useful for lexical candidate discovery, but requiring a choice
    to match would turn an unknown correct option into a hidden ranking label.
    The hard gate therefore uses only the stem.  It deliberately stays lexical:
    it is a fail-closed review filter, never a claim verifier.
    """
    return {term for term in terms(row["question"]["stem"]) if term not in QUESTION_FORM_TERMS}


def _anchor_terms(row: dict) -> set[str]:
    """Extract non-generic named/date anchors from the question root only."""
    raw = CAPITALISED_TOKEN.findall(row["question"]["stem"])
    return {
        term
        for token in raw
        for term in terms(token)
        if term not in QUESTION_FORM_TERMS | GENERIC_CLAIM_TERMS
    }


def _term_matches(claim: str, observed: str) -> bool:
    """Allow a conservative Turkish suffix/root match for long tokens."""
    return claim == observed or (
        len(claim) >= 5 and len(observed) >= 5 and claim[:5] == observed[:5]
    )


def _claim_coverage(row: dict, text: str) -> dict:
    claim_terms = _claim_terms(row)
    observed_terms = set(terms(text))
    covered = sorted(
        claim
        for claim in claim_terms
        if any(_term_matches(claim, observed) for observed in observed_terms)
    )
    distinctive = {
        term for term in claim_terms if len(term) >= 6 or any(char.isdigit() for char in term)
    }
    covered_distinctive = sorted(term for term in distinctive if term in covered)
    anchors = _anchor_terms(row)
    covered_anchors = sorted(term for term in anchors if term in covered)
    required = 1 if len(claim_terms) <= 3 else 2
    # A lexical overlap is a review signal. It does not prove a historical
    # relation or authorize a passage, especially with Turkish OCR noise.
    direct_gate = (
        len(covered) >= required
        and len(covered) / max(1, len(claim_terms)) >= 0.4
        and (not distinctive or bool(covered_distinctive))
        and (not anchors or bool(covered_anchors))
    )
    return {
        "claim_term_count": len(claim_terms),
        "covered_claim_term_count": len(covered),
        "claim_coverage": round(len(covered) / max(1, len(claim_terms)), 3),
        "distinctive_claim_term_count": len(distinctive),
        "covered_distinctive_term_count": len(covered_distinctive),
        "anchor_term_count": len(anchors),
        "covered_anchor_term_count": len(covered_anchors),
        "lexical_overlap_hint": direct_gate,
    }


def _global_index(pool: list[tuple[dict, dict]]) -> PreparedBM25:
    """One indexed corpus for all eligible books, preserving source IDs."""
    items = [
        {
            **chunk,
            "id": f"{book['source_checksum']}:{chunk['id']}",
            "_chunk_id": chunk["id"],
            "_book": book,
        }
        for book, chunk in pool
    ]
    return PreparedBM25(items)


def build(transcriptions: dict, corpus: dict, limit: int = 6) -> dict:
    if transcriptions.get("schema") not in TRANSCRIPTION_SCHEMAS:
        raise ValueError("Private OGM transkripsiyon şeması gerekli")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("MEB corpus şeması geçersiz")
    if limit < 1:
        raise ValueError("Kanıt aday sınırı pozitif olmalı")
    pool = _eligible(corpus)
    index = _global_index(pool)
    proposals = []
    for row in transcriptions.get("rows", []):
        started = time.perf_counter()
        if row.get("transcription_status") != "private_teacher_review_required":
            proposals.append(
                {
                    "candidate_id": row["candidate_id"],
                    "status": "blocked_transcription_quality",
                    "suggestions": [],
                }
            )
            continue
        suggestions = []
        scoped_pool = _topic_pool(pool, row["topic"])
        scoped_ids = {(book["source_checksum"], chunk["id"]) for book, chunk in scoped_pool}
        # Rank *once* across the corpus. Single-document BM25 has no useful
        # collection IDF and makes scores between books incomparable.
        ranked = index.rank(_query(row), limit=len(pool))
        local_ranked = [
            item
            for item in ranked
            if (item["_book"]["source_checksum"], item["_chunk_id"]) in scoped_ids
        ][:limit]
        expanded_ranked = [
            item
            for item in ranked
            if (item["_book"]["source_checksum"], item["_chunk_id"]) not in scoped_ids
        ]
        selected_ranked = local_ranked + expanded_ranked[: limit - len(local_ranked)]
        for item in selected_ranked:
            book = item["_book"]
            in_topic = (book["source_checksum"], item["_chunk_id"]) in scoped_ids
            coverage = _claim_coverage(row, item["text"])
            suggestions.append(
                {
                    "chunk_id": item["_chunk_id"],
                    "source_name": book["source_name"],
                    "source_checksum": book["source_checksum"],
                    "grade": book["grade"],
                    # Older private indexes may not carry a stable section id;
                    # keep the candidate usable for teacher review while
                    # preserving the human-readable section title.
                    "section_id": item.get("section_id") or item.get("section_title", "belirsiz"),
                    "page": item["page"],
                    "bbox": item["bbox"],
                    "section_title": item["section_title"],
                    "score": item["score"],
                    "claim_coverage": coverage,
                    "in_topic_section": in_topic,
                    "text": item["text"],
                    "review_status": "candidate_unverified",
                }
            )
        # Calculate diagnostic coverage only for the selected review slate;
        # it cannot promote a passage over the corpus-wide BM25 ordering.
        proposals.append(
            {
                "candidate_id": row["candidate_id"],
                "topic": row["topic"],
                "status": "teacher_agent_source_review_required"
                if suggestions
                else "insufficient_evidence",
                "section_scope_applied": bool(scoped_pool),
                "expanded_to_other_sections": len(selected_ranked) > len(local_ranked),
                "retrieval_ms": round((time.perf_counter() - started) * 1000, 2),
                "suggestions": suggestions,
            }
        )
    return {
        "schema": SCHEMA,
        "source_checksum": transcriptions["source_checksum"],
        "corpus_checksum": corpus["corpus_checksum"],
        "proposals": proposals,
        "notice": (
            "Private review queue. Lexical coverage is diagnostic only. Suggestions require "
            "PDF-crop and relation review; no answer or worked explanation was read."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    result = build(
        json.loads(args.transcriptions.read_text(encoding="utf-8")),
        json.loads(args.corpus.read_text(encoding="utf-8")),
        args.limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
