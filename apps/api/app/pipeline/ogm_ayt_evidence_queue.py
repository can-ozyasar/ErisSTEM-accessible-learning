"""Build a private MEB-evidence review queue for transcribed OGM AYT items."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..history_rag import rank_chunks

SCHEMA = "ogm-ayt-evidence-review-queue-v1"
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
            suggestions.append({
                "chunk_id": item["id"], "source_name": book["source_name"], "source_checksum": book["source_checksum"],
                "page": item["page"], "bbox": item["bbox"], "section_title": item["section_title"],
                "score": item["score"], "text": item["text"], "review_status": "candidate",
            })
        suggestions.sort(key=lambda item: (-item["score"], item["page"], item["chunk_id"]))
        proposals.append({"candidate_id": row["candidate_id"], "topic": row["topic"],
                          "status": "teacher_agent_source_review_required" if suggestions else "insufficient_evidence",
                          "section_scope_applied": True, "suggestions": suggestions[:limit]})
    return {"schema": SCHEMA, "source_checksum": transcriptions["source_checksum"],
            "corpus_checksum": corpus["corpus_checksum"], "proposals": proposals,
            "notice": "Private review queue. Suggestions are not source approvals; no answer or worked explanation was read."}


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
