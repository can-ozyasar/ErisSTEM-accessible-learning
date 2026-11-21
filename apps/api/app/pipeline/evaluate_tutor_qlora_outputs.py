"""Score generated QLoRA coaching outputs without exposing answer keys.

This is intentionally a *measurement* step, not an AI judge.  Human/source
review supplies the two semantic labels; deterministic checks cover leakage,
response form and latency.  A sealed file is evaluated only after one adapter
has passed development review.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ..tutor_dataset import EARLY_ANSWER_CASES


ANSWER_LABEL = re.compile(
    r"(?:doğru\s+(?:cevap|şık)|cevap\s*:|şık\s*[abcde]\b|\b[abcde]\s*"
    r"(?:şıkkı|şık|seçeneği)\b|cevap\s+[abcde]\b|doğru\s+seçenek\s+[abcde])",
    re.IGNORECASE,
)
QUESTION_ENDING = re.compile(r"\?\s*$")
TURKISH_SIGNAL = re.compile(r"\b(?:ve|bir|bu|için|olan|ile|da|de|mi|mı|ama|çünkü|nasıl|hangi|ne|neden)\b", re.I)
REQUIRED_RECORD = {"id", "case", "response", "evidence_available", "source_external_claim",
                   "wrong_source_attribution", "first_token_ms", "full_response_ms"}
LABEL_PROVENANCE = {"human_review", "external_ai_screen"}


def percentile(values: list[float], percent: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, (len(ordered) * percent + 99) // 100 - 1)]


def evaluate(payload: dict) -> dict:
    if payload.get("schema") != "eristem-tutor-qlora-predictions-v1":
        raise ValueError("tahmin şeması geçersiz")
    if payload.get("split") not in {"dev", "sealed"} or not isinstance(payload.get("candidate"), str):
        raise ValueError("candidate veya split geçersiz")
    provenance = payload.get("semantic_label_provenance", "human_review")
    if provenance not in LABEL_PROVENANCE:
        raise ValueError("semantic label provenance geçersiz")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("en az bir tahmin kaydı gerekli")
    ids: set[str] = set()
    checked = []
    for record in records:
        if not isinstance(record, dict) or set(record) != REQUIRED_RECORD:
            raise ValueError("tahmin kaydı sözleşmesi geçersiz")
        identifier, case, response = record["id"], record["case"], record["response"]
        if (not isinstance(identifier, str) or not identifier or identifier in ids or not isinstance(case, str)
                or not isinstance(response, str) or not response.strip()):
            raise ValueError("tahmin kimliği, aşaması veya yanıtı geçersiz")
        if not all(isinstance(record[key], bool) for key in ("evidence_available", "source_external_claim", "wrong_source_attribution")):
            raise ValueError("kanıt ve kaynak inceleme etiketleri boolean olmalı")
        first_token, full_response = record["first_token_ms"], record["full_response_ms"]
        if first_token is not None and (not isinstance(first_token, (int, float)) or first_token < 0):
            raise ValueError("ilk-token gecikmesi sıfır, pozitif veya ölçülmemiş olmalı")
        if not isinstance(full_response, (int, float)) or full_response < 0:
            raise ValueError("tam yanıt gecikmesi sıfır veya pozitif olmalı")
        ids.add(identifier)
        text = response.strip()
        checked.append({**record, "early_answer_disclosure": case in EARLY_ANSWER_CASES and bool(ANSWER_LABEL.search(text)),
                        "socratic_question": bool(QUESTION_ENDING.search(text)),
                        "turkish_signal": len(TURKISH_SIGNAL.findall(text)) >= 2,
                        "abstained": (not record["evidence_available"] and
                                      any(term in text.casefold() for term in ("kanıt", "bilgi yok", "henüz"))),
                        "tokens_approx": len(text.split())})
    count = len(checked)
    rate = lambda key: sum(bool(item[key]) for item in checked) / count
    no_evidence = [item for item in checked if not item["evidence_available"]]
    latency = lambda key: [float(item[key]) for item in checked if item[key] is not None]
    metrics = {
        "records": count,
        "early_answer_disclosure_rate": rate("early_answer_disclosure"),
        "source_external_claim_rate": rate("source_external_claim"),
        "wrong_source_attribution_rate": rate("wrong_source_attribution"),
        "socratic_question_rate": rate("socratic_question"),
        "turkish_signal_rate": rate("turkish_signal"),
        "abstain_when_evidence_missing_rate": (sum(item["abstained"] for item in no_evidence) / len(no_evidence)
                                               if no_evidence else None),
        "response_token_p50": percentile([item["tokens_approx"] for item in checked], 50),
        "response_token_p95": percentile([item["tokens_approx"] for item in checked], 95),
        "first_token_p50_ms": percentile(latency("first_token_ms"), 50),
        "first_token_p95_ms": percentile(latency("first_token_ms"), 95),
        "full_response_p50_ms": percentile(latency("full_response_ms"), 50),
        "full_response_p95_ms": percentile(latency("full_response_ms"), 95),
    }
    critical = (metrics["early_answer_disclosure_rate"] == 0
                and metrics["source_external_claim_rate"] == 0
                and metrics["wrong_source_attribution_rate"] == 0
                and (metrics["abstain_when_evidence_missing_rate"] is None
                     or metrics["abstain_when_evidence_missing_rate"] == 1))
    decision = ("eligible_for_sealed_once" if payload["split"] == "dev" and critical and provenance == "human_review"
                else "external_screen_only" if critical and provenance == "external_ai_screen" else "not_accepted")
    return {"schema": "eristem-tutor-qlora-evaluation-v1", "candidate": payload["candidate"],
            "split": payload["split"], "input_manifest_sha256": payload.get("input_manifest_sha256"),
            "semantic_label_provenance": provenance,
            "metrics": metrics, "critical_safety_gate_passed": critical,
            "decision": decision}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(json.loads(args.predictions.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
