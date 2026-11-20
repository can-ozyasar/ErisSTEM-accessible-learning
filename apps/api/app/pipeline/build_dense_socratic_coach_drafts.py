"""Create answer-key-free two-turn deterministic coaching drafts from evidence bundles."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ..question_scope import visual_dependency_reasons
from ..tutor_coach import CoachContext, coach


def _error_type(question: str) -> str:
    text = question.casefold()
    if re.search(r"\b(yıl|tarih|dönem|yüzyıl)\b", text):
        return "tarih"
    if re.search(r"\b(neden|sonuç|etki|sebep)\b", text):
        return "neden_sonuc"
    if re.search(r"\b(önce|sonra|sıra|kronoloj)\b", text):
        return "kronoloji"
    if re.search(r"\b(kim|kişi|hükümdar|lider)\b", text):
        return "kisi"
    return "genel"


def build(candidates: dict, calibration: dict, transcriptions: dict) -> dict:
    if candidates.get("schema") != "ayt-dense-coach-candidates-v1":
        raise ValueError("Dense koç aday paketi gerekli")
    if candidates.get("source_checksum") != calibration.get("source_checksum") or candidates.get("corpus_checksum") != calibration.get("corpus_checksum"):
        raise ValueError("Koç adayları ve kalibrasyon sürümleri eşleşmiyor")
    queries = {row.get("id"): row.get("query") for row in calibration.get("queries", [])}
    if transcriptions.get("schema") != "ogm-ayt-private-transcription-v1" or transcriptions.get("source_checksum") != candidates.get("source_checksum"):
        raise ValueError("Soru görsel-kapsam transkripsiyonu kaynak sürümüyle eşleşmiyor")
    question_rows = {row.get("candidate_id"): row.get("question", {}) for row in transcriptions.get("rows", [])}
    rows = []
    excluded_visual = 0
    for item in candidates.get("candidates", []):
        if item.get("status") != "coach_candidate":
            continue
        question_structure = question_rows.get(item.get("question_id"))
        # No original question structure means visual dependence cannot be
        # ruled out. Fail closed instead of treating OCR text as proof.
        if not isinstance(question_structure, dict) or visual_dependency_reasons(question_structure):
            excluded_visual += 1
            continue
        question, evidence = queries.get(item.get("question_id")), item.get("evidence", [])
        if not isinstance(question, str) or not evidence or not isinstance(evidence[0].get("text"), str):
            raise ValueError("Koç adayı soru veya kanıt taşımıyor")
        # The served coach contract is deliberately bounded to four excerpts:
        # more passages increase spoken-load and cannot fit CoachReply.
        evidence = evidence[:4]
        source_ids = item.get("source_ids", [])[:4]
        context = CoachContext(question_id=item["question_id"], question_text=question, choice_text=None,
                               section_title="AYT Tarih", source_ids=source_ids, evidence=evidence[0]["text"],
                               error_type=_error_type(question),
                               evidence_by_role={"relation": evidence[1]["text"]} if len(evidence) > 1 else {})
        first = coach(context, None, "", False, None, None)
        second = coach(context, first.stage, "", False, None, None)
        rows.append({"question_id": item["question_id"], "evidence_mode": item["evidence_mode"],
                     "source_ids": source_ids, "turns": [
                         {"turn": 1, "stage": first.stage, "prompt": first.student_prompt, "source_ids": first.source_ids},
                         {"turn": 2, "stage": second.stage, "prompt": second.student_prompt, "source_ids": second.source_ids},
                     ]})
    if not rows:
        raise ValueError("Koçluk için kaynak-yeterli aday yok")
    return {"schema": "ayt-dense-socratic-coach-drafts-v1", "source_checksum": candidates["source_checksum"],
            "corpus_checksum": candidates["corpus_checksum"], "records": rows,
            "summary": {"record_count": len(rows), "turn_count": len(rows) * 2,
                        "visual_or_unknown_question_excluded": excluded_visual},
            "answer_key_accessed": False, "worked_explanation_accessed": False,
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Two-turn deterministic source-bound coaching drafts; no answer or explanation is disclosed."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build(load(args.candidates), load(args.calibration), load(args.transcriptions))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
