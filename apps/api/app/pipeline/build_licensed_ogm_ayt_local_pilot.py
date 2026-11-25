"""Assemble a non-public, license-record-bound OGM AYT local pilot pack."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build(questions: dict, answers: dict, evidence: dict, usage: dict, sources: dict) -> dict:
    if questions.get("schema") != "ayt-target-question-candidates-v1":
        raise ValueError("OGM soru aday paketi gerekli")
    checksum = questions.get("source_checksum")
    if (answers.get("source_checksum") != checksum or evidence.get("source_checksum") != checksum
            or usage.get("source_checksum") != checksum):
        raise ValueError("soru, cevap anahtarı, kanıt ve kullanım kaydı checksum zinciri bozuk")
    if usage.get("scope") != "local_pilot_only" or usage.get("local_pilot_confirmed") is not True:
        raise ValueError("yalnız doğrulanmış yerel pilot kullanım kaydı kabul edilir")
    if usage.get("student_publication_allowed") is not False:
        raise ValueError("yerel pilot paketi öğrenci/genel yayın izni iddia edemez")
    if sources.get("schema") != "ayt-history-meb-source-catalog-v1":
        raise ValueError("MEB kaynak kataloğu gerekli")
    question_by_id = {row["candidate_id"]: row for row in questions.get("rows", [])}
    answer_by_id = {row["candidate_id"]: row for row in answers.get("records", [])}
    source_by_id = {row["id"]: row for row in sources.get("sources", [])}
    output, source_ids = [], set()
    for item in evidence.get("questions", []):
        identifier = item["candidate_id"]
        raw, answer = question_by_id.get(identifier), answer_by_id.get(identifier)
        if raw is None or answer is None:
            raise ValueError(f"kanıt sorusu kaynak metin veya anahtarla eşleşmiyor: {identifier}")
        question = raw.get("question", {})
        parts = question.get("parts", [])
        stem = "\n\n".join(part.get("text", "").strip() for part in parts if part.get("text", "").strip())
        choices = question.get("choices", [])
        if not stem or len(choices) != 5 or [choice.get("label") for choice in choices] != list("ABCDE"):
            raise ValueError(f"soru metni veya beşli şık yapısı bozuk: {identifier}")
        bundle = []
        for proof in item.get("evidence_bundle", []):
            source = source_by_id.get(proof.get("source_name"))
            if source is None or source.get("source_checksum") != proof.get("source_checksum"):
                raise ValueError(f"MEB kanıtı katalogla eşleşmiyor: {identifier}")
            source_ids.add(source["id"])
            bundle.append({"source_checksum": proof["source_checksum"], "page": proof["page"], "bbox": proof["bbox"],
                           "source_id": source["id"], "source_kind": "meb_textbook", "quote": proof["excerpt"],
                           "role": "primary" if not bundle else "context"})
        if not 1 <= len(bundle) <= 3:
            raise ValueError(f"kanıt demeti 1–3 parça olmalı: {identifier}")
        output.append({"id": "licensed-" + hashlib.sha256(identifier.encode()).hexdigest()[:20],
                       "authorship": "licensed_local_pilot", "review_method": "license_bound_pdf_crop_review",
                       "review_artifact_checksum": _digest(item), "topic": "AYT Tarih", "outcome": "Kaynaklı tarih sorusu çözme",
                       "split": "pilot", "question": stem, "spoken_question": stem,
                       "choices": [choice["text"] for choice in choices], "correct_label": answer["correct_choice"],
                       "explanation": "Kaynaklı açıklama iki koçluk turundan sonra açılır.", "evidence": bundle,
                       "visual_dependency": False, "visual_description_reviewed": False, "status": "approved"})
    if not output:
        raise ValueError("kanıtı tam soru yok")
    return {"schema": "ayt-history-exam-pack-v1", "pack_id": "ogm-ayt-history-local-pilot-v1",
            "content_mode": "licensed_local_pilot", "licensed_question_source_checksum": checksum,
            "license_record_checksum": _digest(usage), "student_publication_allowed": False,
            "sources": [source_by_id[key] for key in sorted(source_ids)], "questions": output}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True); parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True); parser.add_argument("--usage", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.questions), load(args.answers), load(args.evidence), load(args.usage), load(args.sources))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"question_count": len(result["questions"]), "runtime_enabled": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
