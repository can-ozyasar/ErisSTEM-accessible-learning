"""Check the internal consistency of a strict agent sample; no source approval."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

VERDICTS = {"direct", "partial", "irrelevant", "uncertain"}
OUTCOMES = {"reretrieve", "abstain", "crop_review_required_before_use"}


def validate(queue: dict, audit: dict) -> dict:
    if (queue.get("schema") != "ogm-ayt-evidence-review-queue-v3"
            or audit.get("schema") != "ogm-ayt-agent-quality-audit-v2"
            or any(queue.get(key) != audit.get(key)
                   for key in ("source_checksum", "corpus_checksum"))):
        raise ValueError("Kalite örneklemi kaynak sürümüyle eşleşmiyor")
    for flag in ("is_teacher_approval", "answer_key_accessed", "worked_explanation_accessed",
                 "runtime_enabled", "qlora_enabled"):
        if audit.get(flag) is not False:
            raise ValueError(f"Kalite örnekleminde {flag} false olmalı")
    proposals = {row["candidate_id"]: row for row in queue["proposals"]}
    sample = audit.get("manual_stratified_sample", [])
    if len({row.get("candidate_id") for row in sample}) != len(sample):
        raise ValueError("Örneklemde soru kimliği tekrarı var")
    verdicts: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    for row in sample:
        proposal = proposals.get(row.get("candidate_id"))
        if proposal is None or len(row.get("cards", [])) != len(proposal.get("suggestions", [])):
            raise ValueError("Örneklem sorusu veya kart sayısı kuyrukla uyuşmuyor")
        if row.get("source_approval") is not False or not row.get("manual_finding"):
            raise ValueError("Gerekçeli ön inceleme insan onayı veremez")
        outcome = row.get("corrected_question_outcome")
        if outcome not in OUTCOMES:
            raise ValueError("Soru sonucu geçersiz")
        outcomes[outcome] += 1
        for index, (card, source) in enumerate(zip(row["cards"], proposal["suggestions"]), 1):
            if (card.get("rank") != index or card.get("chunk_id") != source["chunk_id"]
                    or card.get("source_checksum") != source["source_checksum"]):
                raise ValueError("Örneklem kartı kaynak sırasıyla eşleşmiyor")
            verdict = card.get("verdict")
            if verdict not in VERDICTS:
                raise ValueError("Örneklem kart kararı geçersiz")
            verdicts[verdict] += 1
    summary = audit.get("sample_summary", {})
    if (summary.get("questions") != len(sample)
            or summary.get("cards") != sum(verdicts.values())
            or any(summary.get(key, 0) != verdicts[key] for key in VERDICTS)
            or any(summary.get("corrected_outcomes", {}).get(key, 0) != outcomes[key]
                   for key in OUTCOMES)):
        raise ValueError("Örneklem özeti kart kararlarından yeniden hesaplanınca tutarsız")
    return {"schema": "ogm-ayt-agent-quality-validation-v1",
            "question_count": len(sample), "card_count": sum(verdicts.values()),
            "verdict_counts": dict(verdicts), "outcome_counts": dict(outcomes),
            "teacher_approved_count": 0, "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Internal sample arithmetic and source IDs verified; historical truth is not established by this validator."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(json.loads(args.queue.read_text(encoding="utf-8")),
                      json.loads(args.audit.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("question_count", "card_count", "verdict_counts")}))


if __name__ == "__main__":
    main()
