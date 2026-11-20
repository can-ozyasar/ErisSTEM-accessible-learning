"""Independent teacher-style review for six-turn source-bound coaching groups."""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from .deepseek_evidence_judge import _call

SCHEMA = "deepseek-source-bound-coaching-group-review-v1"
VERDICTS = {"accept_for_qlora_candidate", "reject"}


def _request(records: list[dict], model: str) -> dict:
    groups = [{"question_id": row["question_id"], "question": row.get("question", ""), "error_type": row["error_type"],
               "turns": [{"case": turn["case"], "learner_state": turn["learner_state"], "strategy": turn["strategy"],
                          "guide_response": turn["guide_response"], "source_excerpt": turn["evidence_quotes"][0]}
                         for turn in row["turns"]]} for row in records]
    prompt = (
        "Sen görme engelli lise öğrencileri için AYT Tarih koçluğu taslaklarını bağımsız değerlendiren deneyimli "
        "bir öğretmensin. Her altı-turlu grubu yalnız verilen kısa MEB alıntılarına göre değerlendir; dış bilgi "
        "kullanma. Kabul için her tur kaynakla uyumlu, doğal ve yargılamayan Türkçe ile tek küçük düşünme adımı "
        "istemeli; öğrenci durumuna uygun iskele olmalı; doğru cevap veya şık erken verilmemeli. Bir kusur varsa "
        "grubun tamamını reject et. JSON dışında yanıt verme: {\"reviews\":[{\"question_id\":\"...\","
        "\"verdict\":\"accept_for_qlora_candidate|reject\",\"source_grounded\":true,\"natural_turkish\":true,"
        "\"adaptive_scaffold\":true,\"no_early_answer_leakage\":true,\"reason\":\"kısa\"}]}.\n"
        + json.dumps({"groups": groups}, ensure_ascii=False, separators=(",", ":"))
    )
    return {"model": model, "temperature": 0, "max_tokens": 1000,
            "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": prompt}]}


def _parse(body: dict, expected: set[str]) -> list[dict]:
    try:
        rows = json.loads(body["choices"][0]["message"]["content"])["reviews"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Koçluk grup incelemesi geçerli JSON dönmedi") from error
    flags = ("source_grounded", "natural_turkish", "adaptive_scaffold", "no_early_answer_leakage")
    if not isinstance(rows, list) or len(rows) != len(expected) or {row.get("question_id") for row in rows if isinstance(row, dict)} != expected:
        raise ValueError("Her koçluk grubu için tam bağımsız inceleme gerekli")
    for row in rows:
        accepted = all(isinstance(row.get(flag), bool) and row[flag] for flag in flags)
        # A reject with otherwise positive flags is conservative and remains a
        # reject. Only an accept has to satisfy every explicit safety flag.
        if row.get("verdict") not in VERDICTS or (row["verdict"] == "accept_for_qlora_candidate" and not accepted):
            raise ValueError("Koçluk grup inceleme sözleşmesi ihlali")
    return rows


def review(payload: dict, api_key: str, *, offset: int = 0, limit: int = 2, model: str = "deepseek-chat", timeout_s: float = 45, request_fn=_call) -> dict:
    if payload.get("schema") not in {"ayt-history-source-bound-coaching-drafts-v1", "deepseek-contextual-source-bound-coaching-drafts-v1"}:
        raise ValueError("Kaynak bağlı koçluk taslağı gerekli")
    if not api_key or offset < 0 or not 1 <= limit <= 2:
        raise ValueError("API anahtarı, offset veya limit geçersiz")
    records = payload.get("records", [])[offset:offset + limit]
    if not records:
        raise ValueError("İncelenecek koçluk grubu yok")
    rows = _parse(request_fn(_request(records, model), api_key, timeout_s), {row["question_id"] for row in records})
    return {"schema": SCHEMA, "corpus_checksum": payload["corpus_checksum"], "question_bank_checksum": payload["question_bank_checksum"],
            "offset": offset, "reviews": [{**row, "reviewer": model, "reviewer_kind": "deepseek_history_teacher_coaching_v1", "runtime_enabled": False} for row in rows],
            "summary": {"review_count": len(rows), "verdicts": dict(Counter(row["verdict"] for row in rows))},
            "runtime_enabled": False, "qlora_enabled": False, "notice": "Independent AI review only; accepted groups remain private QLoRA candidates."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--allow-external-private-evaluation", action="store_true")
    args = parser.parse_args()
    if not args.allow_external_private_evaluation: raise SystemExit("Dış servis çağrısı için --allow-external-private-evaluation zorunlu")
    key = os.getenv(args.api_key_env)
    if not key: raise SystemExit(f"{args.api_key_env} ortam değişkeni tanımlı değil")
    result = review(json.loads(args.input.read_text(encoding="utf-8")), key, offset=args.offset, limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__": main()
