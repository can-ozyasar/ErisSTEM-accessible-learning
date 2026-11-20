"""Apply explicitly reviewed, non-semantic OCR repairs to private coach evidence.

This is deliberately a narrow, manifest-driven step.  It never changes a
question, answer, source coordinate or source checksum; it only replaces an
identified OCR duplication after the original PDF checksum has been checked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize(payload: dict, overrides: dict) -> dict:
    if payload.get("schema") != "deepseek-contextual-source-bound-coaching-drafts-v1":
        raise ValueError("Bağlamsal koç taslağı gerekli")
    rules = {rule["question_id"]: rule for rule in overrides.get("overrides", [])}
    result = deepcopy(payload)
    for record in result.get("records", []):
        rule = rules.get(record.get("question_id"))
        if rule is None:
            continue
        expected_id = f"{rule['source_checksum']}:{rule['atom_id']}"
        for turn in record.get("turns", []):
            if turn.get("source_ids") != [expected_id] or len(turn.get("evidence_quotes", [])) != 1:
                raise ValueError("Kaynak kimliği normalization manifestiyle uyuşmuyor")
            raw = turn["evidence_quotes"][0]
            if rule["raw_fragment"] not in raw:
                raise ValueError("Beklenen OCR bozukluğu taslakta bulunamadı")
            fixed = raw.replace(rule["raw_fragment"], rule["normalized_fragment"])
            if fixed == raw:
                raise ValueError("Normalization değişiklik üretmedi")
            turn["evidence_quotes"] = [fixed]
            turn["evidence_normalization"] = {
                "kind": "reviewed_ocr_duplication_repair",
                "source_checksum": rule["source_checksum"],
                "page": rule["page"],
                "bbox": rule["bbox"],
                "raw_sha256": _digest(raw),
                "normalized_sha256": _digest(fixed),
                "runtime_enabled": False,
            }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
    result = normalize(payload, overrides)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
