"""Validate agent coaching drafts before any production/QLoRA export."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

SCHEMA = "teacher-ogm-ayt-coaching-drafts-v1"
STAGES = ("soru_analizi", "hatırlamayı_ortaya_çıkarma", "kanıtla_bağ_kurma", "şık_sınama", "yanlış_cevap_düzeltme", "doğru_cevabı_gerekçelendirme")
EARLY = set(STAGES[:4])
ANSWER_LEAK = re.compile(r"\b(?:doğru cevap|doğru şık|cevap\s*[:：]|şık\s*[A-E]\b|[A-E]\s*ş(?:ı|i)kk?ı)\b", re.IGNORECASE)


def validate(payload: dict, source_input: dict, *, expected_groups: int | None = None) -> dict:
    if payload.get("schema") != SCHEMA:
        raise ValueError("Koçluk taslağı şeması geçersiz")
    if payload.get("reviewer_kind") != "history_teacher_agent_v1" or payload.get("is_human_teacher_approval") is not False:
        raise ValueError("Agent provenance veya insan onayı alanı geçersiz")
    for key in ("answer_key_accessed", "worked_explanation_accessed", "runtime_enabled", "qlora_enabled"):
        if payload.get(key) is not False:
            raise ValueError(f"Güvenlik alanı kapalı olmalı: {key}")
    allowed = {r["question_id"]: {e["source_id"]: e["excerpt"] for e in r.get("evidence", [])}
               for r in source_input.get("records", [])}
    records = payload.get("records", [])
    by_question: dict[str, dict[str, dict]] = {}
    for row in records:
        qid, stage = row.get("question_id"), row.get("stage")
        if qid not in allowed or stage not in STAGES or stage in by_question.setdefault(qid, {}):
            raise ValueError("Soru/stage kaydı eksik veya tekrarlı")
        if row.get("early_answer_disclosed") is not False or row.get("answer_key_or_gold_choice_included") is not False:
            raise ValueError("Koçluk taslağında cevap ifşası işaretlenmiş")
        ids, quotes = row.get("source_ids", []), row.get("evidence_quotes", [])
        if not 1 <= len(ids) <= 2 or len(ids) != len(quotes) or len(set(ids)) != len(ids):
            raise ValueError("Her turda bir veya iki benzersiz kaynak ve alıntı gerekli")
        if any(source_id not in allowed[qid] or quote not in allowed[qid][source_id] for source_id, quote in zip(ids, quotes)):
            raise ValueError("Alıntı, aynı sorunun onaylanmamış kaynağından geliyor")
        if stage in EARLY and ANSWER_LEAK.search(row.get("guide_response", "")):
            raise ValueError("İlk dört aşamada cevap/şık ifşası")
        if row.get("status") != "ready_for_agent_review":
            raise ValueError("Taslak inceleme durumu geçersiz")
        by_question[qid][stage] = row
    complete = {qid for qid, stages in by_question.items() if set(stages) == set(STAGES)}
    groups = expected_groups if expected_groups is not None else len(complete)
    if len(complete) != groups or len(records) != groups * len(STAGES):
        raise ValueError("Her soru için altı koçluk aşaması gerekli")
    summary = {"question_groups": len(complete), "record_count": len(records), "stages": list(STAGES), "security_passed": True}
    return {"schema": "ogm-ayt-coaching-draft-validation-v1", **summary}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-groups", type=int)
    args = parser.parse_args()
    result = validate(json.loads(args.input.read_text(encoding="utf-8")), json.loads(args.source_input.read_text(encoding="utf-8")), expected_groups=args.expected_groups)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
