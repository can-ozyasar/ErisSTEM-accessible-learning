"""Export a small, agent-reviewed, source-bound QLoRA research pilot.

This deliberately differs from the 120-question production exporter: it
accepts only explicitly labelled research drafts, records their weaker review
status, and cannot mark a production model ready.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..tutor_coach import ANSWER_LABEL
from ..tutor_dataset import CASES, EARLY_ANSWER_CASES


def _question_texts(transcriptions: dict) -> dict[str, str]:
    if transcriptions.get("schema") != "ogm-ayt-private-transcription-v1":
        raise ValueError("Özel soru transkripsiyonu gerekli")
    result = {}
    for row in transcriptions.get("rows", []):
        question = row.get("question", {})
        result[row.get("candidate_id")] = " ".join(
            item for item in [question.get("stem", ""), *(choice.get("text", "") for choice in question.get("choices", []))]
            if item
        )
    return result


def _canonical_records(payload: dict, questions: dict[str, str]) -> list[dict]:
    if payload.get("answer_key_accessed") is not False or payload.get("worked_explanation_accessed") is not False:
        raise ValueError("Cevap anahtarı veya çözümlü kaynak erişimli taslak kabul edilmez")
    records = payload.get("records", [])
    output = []
    for row in records:
        case = row.get("case", row.get("stage"))
        evidence = row.get("source_evidence", [])
        source_ids = row.get("source_ids") or [item.get("source_id") for item in evidence]
        quotes = row.get("evidence_quotes") or [item.get("quote") for item in evidence]
        response = row.get("guide_response", row.get("coach_response", ""))
        if case not in CASES or not isinstance(response, str) or not response.strip():
            raise ValueError("Pilot koçluk aşaması veya yanıtı geçersiz")
        if len(source_ids) not in {1, 2} or len(source_ids) != len(quotes):
            raise ValueError("Pilotun her turunda bir veya iki kaynak alıntısı gerekli")
        if any(not isinstance(value, str) or not value.strip() or len(value) > 520 for value in quotes):
            raise ValueError("Pilot kaynak alıntısı geçersiz")
        if (case in EARLY_ANSWER_CASES
                and (row.get("early_answer_disclosed") is True or row.get("answer_revealed") is True
                     or ANSWER_LABEL.search(response))):
            raise ValueError("Erken koçluk aşamasında cevap veya şık ifşası var")
        question_id = row.get("question_id")
        if question_id not in questions:
            raise ValueError("Pilot sorusu private transkripsiyonda bulunamadı")
        output.append({
            "group_id": question_id, "case": case, "error_type": row.get("error_type", "genel"),
            "question": row.get("question_text", questions[question_id]),
            "learner_state": row.get("learner_state", row.get("student_assumption", "Öğrenci bağlantıyı kurmaya çalışıyor.")),
            "quotes": quotes, "completion": response,
        })
    return output


def build(drafts: list[dict], transcriptions: dict) -> tuple[dict[str, list[dict]], dict]:
    questions = _question_texts(transcriptions)
    rows = [item for draft in drafts for item in _canonical_records(draft, questions)]
    grouped: dict[str, dict[str, dict]] = {}
    for row in rows:
        if row["case"] in grouped.setdefault(row["group_id"], {}):
            raise ValueError("Pilot soru grubunda aşama tekrarı var")
        grouped[row["group_id"]][row["case"]] = row
    complete = {key: value for key, value in grouped.items() if set(value) == set(CASES)}
    if len(complete) < 10:
        raise ValueError("Pilot için en az 10 tam kaynak bağlı soru grubu gerekli")
    ordered = sorted(complete, key=lambda item: hashlib.sha256(item.encode()).hexdigest())
    dev_count = max(2, round(len(ordered) * 0.25))
    buckets = {"train": [], "dev": []}
    for index, question_id in enumerate(ordered):
        split = "dev" if index < dev_count else "train"
        for case in CASES:
            row = complete[question_id][case]
            prompt = "\n".join((
                "Sen lise tarih soru koçusun. Öğrenciyi düşündür; kısa ve doğal Türkçe kullan.",
                "Koçluk durumu: " + row["case"], "Hata türü: " + row["error_type"],
                "Soru: " + row["question"], "Öğrenci: " + row["learner_state"],
                "MEB kanıtı: " + " ".join(row["quotes"]), "Koç:",
            ))
            buckets[split].append({key: row[key] for key in ("group_id", "case", "error_type")} | {"prompt": prompt, "completion": row["completion"]})
    report = {"schema": "history-tutor-qlora-pilot-v1", "status": "research_ready",
              "review_status": "agent_reviewed_only", "question_groups": len(complete),
              "examples": len(rows), "splits": {key: len(value) for key, value in buckets.items()},
              "production_ready": False, "runtime_enabled": False, "qlora_enabled": False,
              "notice": "Research pilot only; it does not replace the 120-group production acceptance gate."}
    return buckets, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", type=Path, action="append", required=True)
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    buckets, report = build([load(path) for path in args.draft], load(args.transcriptions))
    args.output.mkdir(parents=True, exist_ok=True)
    for split, rows in buckets.items():
        (args.output / f"{split}.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    (args.output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
