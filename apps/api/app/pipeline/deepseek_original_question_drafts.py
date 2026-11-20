"""Generate source-bound original-question drafts, never a live exam package."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from ..question_scope import visual_dependency_reasons
from .deepseek_evidence_judge import _call

SCHEMA = "deepseek-original-question-drafts-v1"
LABELS = "ABCDE"


def _balance_choice_positions(rows: list[dict]) -> list[dict]:
    """Move a model's correct option to a stable, near-uniform position.

    The model is asked for semantically valid choices, but tends to emit its
    supported answer in A.  This permutation never changes choice content or
    correctness; it simply prevents a positional-answer pattern in drafts.
    """
    balanced = []
    for row in rows:
        choices = list(row["choices"])
        correct_index = LABELS.index(row["correct_label"])
        target_index = int(hashlib.sha256(row["id"].encode("utf-8")).hexdigest(), 16) % len(LABELS)
        correct_choice = choices[correct_index]
        choices.pop(correct_index)
        choices.insert(target_index, correct_choice)
        balanced.append({**row, "choices": choices, "correct_label": LABELS[target_index]})
    return balanced


def _request(cards: list[dict], model: str) -> dict:
    sources = [{"id": item["card"]["id"], "excerpt": item["card"]["source_evidence"]["quote"]}
               for item in cards]
    prompt = (
        "Sen erişilebilir AYT Tarih için özgün soru taslağı yazan bir öğretmensin. Her kaynak alıntısı için yalnız "
        "o alıntıyla çözülebilecek, tamamen yeni bir Türkçe çoktan seçmeli soru üret. Dış bilgi kullanma; harita, "
        "tablo, görsel, şekil, grafiğe atıf yapma; kaynak metnini uzun biçimde kopyalama; cevap açıklamasını soru "
        "köküne koyma. Beş şık benzersiz olsun ve yalnız bir şık kaynakla açıkça desteklensin. Her id bir kez dönsün. "
        "JSON dışında yanıt verme: {\"drafts\":[{\"id\":\"...\",\"question\":\"...\",\"spoken_question\":\"...\","
        "\"choices\":[\"...\",\"...\",\"...\",\"...\",\"...\"],\"correct_label\":\"A|B|C|D|E\","
        "\"explanation\":\"Kaynağa bağlı kısa açıklama\"}]}.\n"
        + json.dumps({"sources": sources}, ensure_ascii=False, separators=(",", ":"))
    )
    return {"model": model, "temperature": 0, "max_tokens": 3800,
            "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": prompt}]}


def _parse(response: dict, expected: set[str]) -> list[dict]:
    try:
        rows = json.loads(response["choices"][0]["message"]["content"])["drafts"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("DeepSeek soru taslakları geçerli JSON dönmedi") from error
    if not isinstance(rows, list) or {row.get("id") for row in rows if isinstance(row, dict)} != expected or len(rows) != len(expected):
        raise ValueError("Her kaynak kartı için tam bir soru taslağı gerekli")
    for row in rows:
        question, spoken, choices, label, explanation = (row.get("question"), row.get("spoken_question"),
                                                          row.get("choices"), row.get("correct_label"), row.get("explanation"))
        if not all(isinstance(item, str) and item.strip() for item in (question, spoken, explanation)):
            raise ValueError("Soru metni, sesletim ve açıklama gerekli")
        if not isinstance(choices, list) or len(choices) != 5 or any(not isinstance(item, str) or not item.strip() for item in choices):
            raise ValueError("Beş boş olmayan şık gerekli")
        if len({item.strip().casefold() for item in choices}) != 5 or label not in LABELS:
            raise ValueError("Şıklar benzersiz ve doğru cevap etiketi geçerli olmalı")
        if visual_dependency_reasons({"stem": question, "choices": choices}):
            raise ValueError("Görsel/tablo bağımlı taslak reddedildi")
    return rows


def draft(gate: dict, api_key: str, *, model: str = "deepseek-chat", offset: int = 0,
          limit: int = 5, timeout_s: float = 45, request_fn=_call) -> dict:
    if gate.get("schema") != "ayt-history-authoring-source-gate-v1":
        raise ValueError("PDF crop inceleme kuyruğu gerekli")
    if not isinstance(gate.get("queue_checksum"), str) or len(gate["queue_checksum"]) != 64:
        raise ValueError("Kaynak kuyruğu checksum'ı gerekli")
    if not api_key or offset < 0 or not 1 <= limit <= 5:
        raise ValueError("API anahtarı, offset veya limit geçersiz")
    cards = gate.get("accepted_for_pdf_crop_review", [])[offset:offset + limit]
    if not cards or any(item.get("pdf_crop_review_required") is not True for item in cards):
        raise ValueError("Yalnız PDF crop incelemesi zorunlu kaynak kartları taslak girdisi olabilir")
    rows = _parse(request_fn(_request(cards, model), api_key, timeout_s), {item["card"]["id"] for item in cards})
    rows = _balance_choice_positions(rows)
    by_id = {item["card"]["id"]: item for item in cards}
    return {"schema": SCHEMA, "corpus_checksum": gate["corpus_checksum"],
            "queue_checksum": gate["queue_checksum"], "draft_offset": offset,
            "drafts": [{**row, "authorship": "original", "source_evidence": by_id[row["id"]]["card"]["source_evidence"],
                        "ai_source_review": by_id[row["id"]]["ai_review"], "status": "source_and_crop_review_required",
                        "runtime_enabled": False} for row in rows],
            "summary": {"draft_count": len(rows), "model": model}, "answer_key_accessed": False,
            "worked_explanation_accessed": False, "student_data_accessed": False,
            "is_human_teacher_approval": False, "runtime_enabled": False, "qlora_enabled": False,
            "notice": "AI-authored original-question drafts only; independent source validation is required before use.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=45)
    parser.add_argument("--allow-external-private-evaluation", action="store_true")
    args = parser.parse_args()
    if not args.allow_external_private_evaluation:
        raise SystemExit("Dış servis çağrısı için --allow-external-private-evaluation zorunlu")
    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} ortam değişkeni tanımlı değil")
    result = draft(json.loads(args.gate.read_text(encoding="utf-8")), api_key, model=args.model,
                   offset=args.offset, limit=args.limit, timeout_s=args.timeout_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
