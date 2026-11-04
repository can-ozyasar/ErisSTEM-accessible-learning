"""Merge bounded history-teacher-agent source reviews into private Gold labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ogm_ayt_retrieval_gold import REVIEWER_KINDS, SCHEMA, source_key


def merge(queue: dict, batches: list[dict]) -> dict:
    if queue.get("schema") != "ogm-ayt-evidence-review-queue-v3":
        raise ValueError("Sürümlü AYT kanıt kuyruğu gerekli")
    cases: list[dict] = []
    expected = {row["candidate_id"]: {source_key(item) for item in row.get("suggestions", [])}
                for row in queue.get("proposals", [])}
    for batch in batches:
        if (batch.get("source_checksum") != queue.get("source_checksum")
                or batch.get("corpus_checksum") != queue.get("corpus_checksum")):
            raise ValueError("Ajan onay partisinin kaynak sürümü değişmiş")
        for key in ("is_teacher_approval", "answer_key_accessed", "worked_explanation_accessed",
                    "runtime_enabled", "qlora_enabled"):
            if batch.get(key) is not False:
                raise ValueError(f"Ajan onay partisinde {key} false olmalı")
        cases.extend(batch.get("reviews", []))
    if len(cases) != len(expected) or {case.get("candidate_id") for case in cases} != set(expected):
        raise ValueError("Ajan Gold birleşimi tüm soru gruplarını tam bir kez içermeli")
    for case in cases:
        candidate_id = case["candidate_id"]
        if (not case.get("reviewed") or not case.get("crop_checked") or not case.get("coverage_complete")
                or case.get("reviewer_kind") != "history_teacher_agent_v1" or not case.get("reviewer")):
            raise ValueError("Ajan Gold kaydında inceleme ve kaynak kesiti kanıtı gerekli")
        judgments = case.get("judgments", [])
        keys = [item.get("source_key") for item in judgments]
        if (len(keys) != len(expected[candidate_id]) or set(keys) != expected[candidate_id]
                or any(item.get("verdict") not in {"support", "wrong"} for item in judgments)):
            raise ValueError("Ajan Gold kararı kuyruktaki altı kaynağı eksiksiz etiketlemeli")
        has_support = any(item["verdict"] == "support" for item in judgments)
        if case.get("abstain") is not (not has_support):
            raise ValueError("Çekimserlik ve destek kararı çelişiyor")
    return {"schema": SCHEMA, "source_checksum": queue["source_checksum"],
            "corpus_checksum": queue["corpus_checksum"], "cases": cases,
            "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Private Gold labels approved by history_teacher_agent_v1; no human approval is claimed."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--batch", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    output = merge(load(args.queue), [load(path) for path in args.batch])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"case_count": len(output["cases"]), "reviewer_kinds": sorted(REVIEWER_KINDS)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
