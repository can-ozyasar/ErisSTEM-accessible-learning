"""Build a private MEB-evidence review queue for transcribed OGM AYT items."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ..history_rag import rank_chunks, terms

SCHEMA = "ogm-ayt-evidence-review-queue-v2"
# These words occur in a question form far more often than they identify a
# historical claim.  They are excluded only from the *literal claim coverage*
# check below.  BM25 continues to see the complete question and choices.
QUESTION_FORM_TERMS = {
    "aşağıdakilerden", "aşağıdaki", "hangisi", "hangilerinden", "hangileri",
    "hangisidir", "verilen", "verilmiştir", "göre", "olarak", "ilgili",
    "değildir", "olamaz", "ulaşılabilir", "söylenebilir", "çıkarılabilir",
    "doğru", "yanlış", "bilgi", "ifadeler", "ifade", "yargı", "yargılardan",
    "özellik", "özelliklerden", "olduğu", "olması", "amaçlanmıştır",
}
GENERIC_CLAIM_TERMS = {
    "türkiye", "dünya", "dönem", "devlet", "savaş", "milli", "mücadele",
    "tarih", "tarihi", "gelişme", "olay", "bilgi", "toplum", "ülke",
}
CAPITALISED_TOKEN = re.compile(r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+|MÖ|MS|\d{3,4}")
TOPIC_SECTION_HINTS = {
    "Millî Mücadele": ("MİLLÎ MÜCADELE", "BÜYÜK MİLLET MECLİSİ", "SEVR", "CEPHELER", "LOZAN"),
    "Atatürkçülük ve Türk İnkılabı": ("ATATÜRK İLKELERİ", "İNKILAP", "ATATÜRK DÖNEMİ", "ATATÜRKÇÜ DÜŞÜNCE"),
    "İki Savaş Arasındaki Dönemde Türkiye ve Dünya": ("İKİ DÜNYA SAVAŞI ARASINDAKİ",),
    "II. Dünya Savaşı Sürecinde Türkiye ve Dünya": ("II. DÜNYA SAVAŞI",),
    "II. Dünya Savaşı Sonrasında Türkiye ve Dünya": ("II. DÜNYA SAVAŞI SONRASI", "1950’LERDE TÜRKİYE"),
    "21. Yüzyılın Eşiğinde Türkiye ve Dünya": ("1960 SONRASI", "1990 SONRASI"),
}


def _normalise(value: str) -> str:
    return " ".join(value.replace("İ", "I").replace("ı", "i").upper().split())


def _topic_pool(pool: list[tuple[dict, dict]], topic: str) -> list[tuple[dict, dict]]:
    hints = TOPIC_SECTION_HINTS.get(topic)
    if not hints:
        return []
    normalized_hints = tuple(_normalise(hint) for hint in hints)
    return [(book, chunk) for book, chunk in pool
            if any(hint in _normalise(chunk.get("section_title", "")) for hint in normalized_hints)]


def _eligible(corpus: dict) -> list[tuple[dict, dict]]:
    rows = []
    for book in corpus.get("books", []):
        if book.get("grade") != 12:
            continue
        for chunk in book["index"].get("chunks", []):
            if chunk.get("pre_review", {}).get("decision") == "review_for_approval" and not chunk.get("quality", {}).get("warnings"):
                rows.append((book, chunk))
    return rows


def _query(row: dict) -> str:
    return " ".join([row["question"]["stem"], *(choice["text"] for choice in row["question"]["choices"])])


def _claim_terms(row: dict) -> set[str]:
    """Return inspectable question-root terms without using an answer key.

    Choices are useful for lexical candidate discovery, but requiring a choice
    to match would turn an unknown correct option into a hidden ranking label.
    The hard gate therefore uses only the stem.  It deliberately stays lexical:
    it is a fail-closed review filter, never a claim verifier.
    """
    return {term for term in terms(row["question"]["stem"])
            if term not in QUESTION_FORM_TERMS}


def _anchor_terms(row: dict) -> set[str]:
    """Extract non-generic named/date anchors from the question root only."""
    raw = CAPITALISED_TOKEN.findall(row["question"]["stem"])
    return {term for token in raw for term in terms(token)
            if term not in QUESTION_FORM_TERMS | GENERIC_CLAIM_TERMS}


def _term_matches(claim: str, observed: str) -> bool:
    """Allow a conservative Turkish suffix/root match for long tokens."""
    return claim == observed or (len(claim) >= 5 and len(observed) >= 5
                                and claim[:5] == observed[:5])


def _claim_coverage(row: dict, text: str) -> dict:
    claim_terms = _claim_terms(row)
    observed_terms = set(terms(text))
    covered = sorted(claim for claim in claim_terms
                     if any(_term_matches(claim, observed) for observed in observed_terms))
    distinctive = {term for term in claim_terms if len(term) >= 6 or any(char.isdigit() for char in term)}
    covered_distinctive = sorted(term for term in distinctive if term in covered)
    anchors = _anchor_terms(row)
    covered_anchors = sorted(term for term in anchors if term in covered)
    required = 1 if len(claim_terms) <= 3 else 2
    # A long/date-like token blocks generic topic prose from passing merely by
    # repeating common historical words such as "Türkiye" or "dönem".
    direct_gate = (len(covered) >= required
                   and len(covered) / max(1, len(claim_terms)) >= 0.4
                   and (not distinctive or bool(covered_distinctive))
                   and (not anchors or bool(covered_anchors)))
    return {
        "claim_term_count": len(claim_terms),
        "covered_claim_term_count": len(covered),
        "claim_coverage": round(len(covered) / max(1, len(claim_terms)), 3),
        "distinctive_claim_term_count": len(distinctive),
        "covered_distinctive_term_count": len(covered_distinctive),
        "anchor_term_count": len(anchors),
        "covered_anchor_term_count": len(covered_anchors),
        "literal_claim_gate": direct_gate,
    }


def build(transcriptions: dict, corpus: dict, limit: int = 6) -> dict:
    if transcriptions.get("schema") != "ogm-ayt-private-transcription-v1":
        raise ValueError("Private OGM transkripsiyon şeması gerekli")
    if corpus.get("schema") != "multi-history-rag-v1":
        raise ValueError("MEB corpus şeması geçersiz")
    if limit < 1:
        raise ValueError("Kanıt aday sınırı pozitif olmalı")
    pool = _eligible(corpus)
    proposals = []
    for row in transcriptions.get("rows", []):
        if row.get("transcription_status") != "private_teacher_review_required":
            proposals.append({"candidate_id": row["candidate_id"], "status": "blocked_transcription_quality", "suggestions": []})
            continue
        suggestions = []
        scoped_pool = _topic_pool(pool, row["topic"])
        for book, chunk in scoped_pool:
            ranked = rank_chunks([chunk], _query(row), limit=1)
            if not ranked:
                continue
            item = ranked[0]
            coverage = _claim_coverage(row, item["text"])
            suggestions.append({
                "chunk_id": item["id"], "source_name": book["source_name"], "source_checksum": book["source_checksum"],
                "page": item["page"], "bbox": item["bbox"], "section_title": item["section_title"],
                "score": item["score"], "claim_coverage": coverage,
                "text": item["text"],
                "review_status": "candidate" if coverage["literal_claim_gate"] else "reretrieve_required",
            })
        # Direct coverage is an explicit gate, then BM25 breaks ties among
        # candidates. This prevents a generic, high-frequency section from
        # becoming a teacher-review lead ahead of a directly relevant passage.
        suggestions.sort(key=lambda item: (-item["claim_coverage"]["literal_claim_gate"],
                                            -item["claim_coverage"]["claim_coverage"],
                                            -item["score"], item["page"], item["chunk_id"]))
        direct = [item for item in suggestions if item["claim_coverage"]["literal_claim_gate"]]
        proposals.append({"candidate_id": row["candidate_id"], "topic": row["topic"],
                          "status": ("teacher_agent_source_review_required" if direct else
                                     "reretrieve_claim_coverage" if scoped_pool else "insufficient_evidence"),
                          "section_scope_applied": True, "suggestions": suggestions[:limit]})
    return {"schema": SCHEMA, "source_checksum": transcriptions["source_checksum"],
            "corpus_checksum": corpus["corpus_checksum"], "proposals": proposals,
            "notice": ("Private review queue. Literal question-root coverage is a fail-closed review gate, "
                       "not source approval; no answer or worked explanation was read.")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    result = build(json.loads(args.transcriptions.read_text(encoding="utf-8")),
                   json.loads(args.corpus.read_text(encoding="utf-8")), args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
