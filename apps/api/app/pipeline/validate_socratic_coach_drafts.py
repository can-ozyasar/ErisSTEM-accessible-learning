"""Fail-closed safety audit for two-turn source-bound coaching drafts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ANSWER = re.compile(r"(?:doğru\s+(?:cevap|şık)|cevap\s*:|\bşık\s*[abcde]\b|\b[abcde]\s*şıkk[ıi])", re.I)


def validate(payload: dict) -> dict:
    if payload.get("schema") != "ayt-dense-socratic-coach-drafts-v1":
        raise ValueError("İki turlu dense koçluk taslağı gerekli")
    if payload.get("answer_key_accessed") is not False or payload.get("worked_explanation_accessed") is not False:
        raise ValueError("Koçluk taslağı cevap anahtarı veya çözüm erişimi taşıyor")
    violations = []
    for record in payload.get("records", []):
        identifier, sources, turns = record.get("question_id"), record.get("source_ids", []), record.get("turns", [])
        if not isinstance(identifier, str) or not sources or len(sources) > 4:
            violations.append({"question_id": identifier, "reason": "invalid_source_bundle"})
            continue
        if len(turns) != 2 or [turn.get("stage") for turn in turns] != ["soru_analizi", "hatirlayani_ortaya_cikar"]:
            violations.append({"question_id": identifier, "reason": "invalid_turn_sequence"})
            continue
        for turn in turns:
            prompt = turn.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip().endswith("?") or ANSWER.search(prompt):
                violations.append({"question_id": identifier, "reason": "unsafe_or_non_socratic_prompt"})
                break
            if turn.get("source_ids") != sources:
                violations.append({"question_id": identifier, "reason": "turn_source_mismatch"})
                break
    return {"schema": "ayt-dense-socratic-coach-audit-v1", "source_checksum": payload["source_checksum"],
            "corpus_checksum": payload["corpus_checksum"], "record_count": len(payload.get("records", [])),
            "violation_count": len(violations), "violations": violations,
            "accepted": not violations, "runtime_enabled": False,
            "notice": "Structural safety audit only; passing does not approve sources or reveal answers."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"accepted": result["accepted"], "violations": result["violation_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
