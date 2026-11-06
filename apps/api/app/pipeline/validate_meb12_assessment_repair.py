"""Validate source-PDF OCR repair before it enters evidence review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def validate(payload: dict, pdf: Path | None = None) -> dict:
    if payload.get("schema") != "ayt-target-question-candidates-v1":
        raise ValueError("MEB aday şeması geçersiz")
    if pdf is not None:
        checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if checksum != payload.get("source_checksum"):
            raise ValueError("Kaynak PDF checksum eşleşmiyor")
    for field in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"):
        if payload.get(field) is not False:
            raise ValueError(f"Güvenlik alanı kapalı olmalı: {field}")
    seen: set[str] = set()
    for row in payload.get("rows", []):
        candidate = row.get("candidate_id")
        if not candidate or candidate in seen:
            raise ValueError("Aday kimlikleri benzersiz olmalı")
        seen.add(candidate)
        if row.get("transcription_status") != "private_pdf_text_repaired":
            raise ValueError("Onarım durumu geçersiz")
        if row.get("answer_key_accessed") is not False or row.get("worked_explanation_accessed") is not False:
            raise ValueError("Aday satırı cevap veya çözüm erişimi içeriyor")
        question = row.get("question", {})
        if not isinstance(question.get("source"), dict) or question["source"].get("source_checksum") != payload.get("source_checksum"):
            raise ValueError("Soru kaynağı checksum ile bağlı değil")
        parts = question.get("parts", [])
        if not parts or not any(part.get("kind") == "stem" and len(part.get("text", "").strip()) >= 8 for part in parts):
            raise ValueError("Soru kökü eksik")
        choices = question.get("choices", [])
        if [choice.get("label") for choice in choices] != list("ABCDE"):
            raise ValueError("A-E seçenek dizisi eksik")
        if any(not choice.get("text", "").strip() for choice in choices):
            raise ValueError("Boş seçenek var")
        forbidden_keys = {"answer", "answer_label", "correct_choice", "solution", "worked_explanation"}
        if forbidden_keys.intersection(row) or forbidden_keys.intersection(question):
            raise ValueError("Cevap anahtarı veya çözüm alanı bulundu")
    return {"schema": "meb12-assessment-repair-validation-v1", "candidate_count": len(seen), "security_passed": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(json.loads(args.input.read_text(encoding="utf-8")), args.pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
