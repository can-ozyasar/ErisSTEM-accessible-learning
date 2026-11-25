"""Build a transparent, local-only extension from AI source-consensus candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.exam_practice import AytHistoryExamPack


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build(base: dict, candidates: dict, questions: dict, usage: dict) -> dict:
    parsed_base = AytHistoryExamPack.model_validate(base)
    if parsed_base.content_mode != "licensed_local_pilot":
        raise ValueError("temel paket izinli yerel pilot olmalı")
    if candidates.get("schema") != "ogm-ayt-history-source-grounded-pilot-candidates-v1":
        raise ValueError("AI kaynak-doğrulamalı aday paketi gerekli")
    checksum = candidates.get("source_checksum")
    if checksum != questions.get("source_checksum") or checksum != usage.get("source_checksum"):
        raise ValueError("aday, soru ve kullanım kaydı checksum zinciri bozuk")
    if usage.get("scope") != "local_pilot_only" or usage.get("local_pilot_confirmed") is not True or usage.get("student_publication_allowed") is not False:
        raise ValueError("yerel pilot kullanım kaydı geçersiz")
    raw_by_id = {row["candidate_id"]: row for row in questions.get("rows", [])}
    source_ids = {source.id for source in parsed_base.sources}
    output = [item.model_dump() for item in parsed_base.questions]
    for item in candidates.get("questions", []):
        identifier = item.get("candidate_id")
        raw = raw_by_id.get(identifier)
        if raw is None:
            raise ValueError("aday soru kaynak metninde bulunamadı")
        question = raw.get("question", {})
        stem = "\n\n".join(part.get("text", "").strip() for part in question.get("parts", []) if part.get("text", "").strip())
        choices = question.get("choices", [])
        if not stem or len(choices) != 5 or [choice.get("label") for choice in choices] != list("ABCDE"):
            raise ValueError("aday soru veya şık yapısı geçersiz")
        evidence = []
        for proof in item.get("evidence_bundle", []):
            if proof.get("source_name") not in source_ids:
                raise ValueError("AI aday kanıtı temel MEB kataloğunda değil")
            evidence.append({"source_checksum": proof["source_checksum"], "page": proof["page"], "bbox": proof["bbox"],
                             "source_id": proof["source_name"], "source_kind": "meb_textbook", "quote": proof["excerpt"],
                             "role": "primary" if not evidence else "context"})
        if not 1 <= len(evidence) <= 3:
            raise ValueError("AI aday kanıt demeti 1–3 parça olmalı")
        output.append({"id": "ai-reviewed-" + hashlib.sha256(identifier.encode()).hexdigest()[:20],
                       "authorship": "ai_source_reviewed_local_pilot", "review_method": "ai_source_consensus_pdf_review",
                       "review_artifact_checksum": candidates.get("review_checksum", _digest(item)), "topic": "AYT Tarih",
                       "outcome": "Kaynaklı tarih sorusu çözme", "split": "pilot", "question": stem, "spoken_question": stem,
                       "choices": [choice["text"] for choice in choices], "correct_label": item["correct_choice"],
                       "explanation": "Kaynaklı açıklama iki koçluk turundan sonra açılır.", "evidence": evidence,
                       "visual_dependency": False, "visual_description_reviewed": False, "status": "approved"})
    result = {"schema": "ayt-history-exam-pack-v1", "pack_id": "ogm-ayt-history-ai-reviewed-local-pilot-v1",
              "content_mode": "ai_source_reviewed_local_pilot", "licensed_question_source_checksum": checksum,
              "license_record_checksum": _digest(usage), "student_publication_allowed": False,
              "sources": [source.model_dump() for source in parsed_base.sources], "questions": output}
    AytHistoryExamPack.model_validate(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True); parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True); parser.add_argument("--usage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.base), load(args.candidates), load(args.questions), load(args.usage))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"question_count": len(result["questions"]), "content_mode": result["content_mode"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
