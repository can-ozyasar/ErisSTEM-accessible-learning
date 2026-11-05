"""Project reviewed private OGM transcriptions into answer-free bundle IDs.

Evidence-bundle discovery only needs stable question identity and topic metadata.
Keeping OCR question text out of this projection prevents the bundle builder
from quietly gaining access to answer-bearing material in a later workflow.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "ayt-tarih2-candidates-v1"
INPUT_SCHEMA = "ogm-ayt-private-transcription-v1"


def build(transcriptions: dict, candidate_ids: list[str]) -> dict:
    if transcriptions.get("schema") != INPUT_SCHEMA:
        raise ValueError("Özel OGM transkripsiyon şeması gerekli")
    if not candidate_ids or len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("En az bir benzersiz soru kimliği gerekli")
    rows = {row.get("candidate_id"): row for row in transcriptions.get("rows", [])}
    if not set(candidate_ids) <= set(rows):
        raise ValueError("Bilinmeyen OGM soru kimliği")
    selected = []
    for candidate_id in candidate_ids:
        row = rows[candidate_id]
        if row.get("answer_key_accessed") is not False or row.get("worked_explanation_accessed") is not False:
            raise ValueError("Cevap anahtarı veya çözüm erişimli soru projeksiyona giremez")
        if row.get("transcription_status") != "private_teacher_review_required":
            raise ValueError("Yalnız inceleme bekleyen özel transkripsiyon kullanılabilir")
        selected.append({
            "candidate_id": candidate_id,
            "exam_year": None,
            "year_status": "bound",
            "topic": row.get("topic", "Başlıksız"),
        })
    return {
        "schema": SCHEMA,
        "source_checksum": transcriptions["source_checksum"],
        "candidate_count": len(selected),
        "candidates": selected,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": ("Answer-free identity projection for private evidence-bundle discovery. "
                   "It approves neither evidence nor a student-facing answer."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--candidate-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.transcriptions.read_text(encoding="utf-8"))
    result = build(payload, args.candidate_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidate_count": result["candidate_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
