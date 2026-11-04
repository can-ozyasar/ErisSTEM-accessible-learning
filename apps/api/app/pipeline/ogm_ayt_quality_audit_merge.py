"""Merge prior and incremental private OCR quality pre-audits fail-closed."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

SCHEMA = "ogm-ayt-full-transcription-quality-gate-agent-audit-v1"
BATCH_SCHEMA = "ogm-ayt-expanded-quality-agent-batch-v1"
STATUSES = {"clear", "recoverable_with_crop", "reject_resplit"}


def _accepted_rows(transcriptions: dict) -> list[dict]:
    if transcriptions.get("schema") != "ogm-ayt-private-transcription-v1":
        raise ValueError("Genişletilmiş private transkripsiyon gerekli")
    return [row for row in transcriptions.get("rows", [])
            if row.get("transcription_status") == "private_teacher_review_required"]


def _validate_common(document: dict, checksum: str, *, legacy_pre_gate: bool = False) -> None:
    if document.get("source_checksum") != checksum:
        raise ValueError("Kalite denetiminde kaynak checksum'ı eşleşmiyor")
    for field in ("is_teacher_approval", "answer_key_accessed", "worked_explanation_accessed",
                  "runtime_enabled", "qlora_enabled"):
        if legacy_pre_gate and field in {"runtime_enabled", "qlora_enabled"} and field not in document:
            continue
        if document.get(field) is not False:
            raise ValueError(f"{field} false olmalı")


def _validate_candidate(row: dict, allowed: dict[str, dict]) -> None:
    candidate_id = row.get("candidate_id")
    source = allowed.get(candidate_id)
    if source is None:
        raise ValueError("Denetimde kaynak dışı aday var")
    if row.get("topic") != source.get("topic") or row.get("page") != source.get("page"):
        raise ValueError("Denetim adayı konu veya sayfa bilgisiyle eşleşmiyor")
    if row.get("transcription_status") not in STATUSES:
        raise ValueError("Geçersiz OCR kalite kararı")
    if row.get("source_approval") != "not_granted":
        raise ValueError("Ajan kaynak onayı veremez")


def _summary(rows: list[dict]) -> dict:
    by_status = Counter(row["transcription_status"] for row in rows)
    by_evidence = Counter(row.get("evidence_suitability", "targeted_retrieval_required") for row in rows)
    by_risk = Counter(row.get("pedagogical_risk", "medium") for row in rows)
    by_topic: dict[str, Counter[str]] = {}
    for row in rows:
        by_topic.setdefault(row["topic"], Counter())[row["transcription_status"]] += 1
    return {"question_count": len(rows), "by_transcription": dict(sorted(by_status.items())),
            "by_evidence": dict(sorted(by_evidence.items())), "by_risk": dict(sorted(by_risk.items())),
            "by_topic": {topic: dict(sorted(counts.items())) for topic, counts in sorted(by_topic.items())}}


def merge(transcriptions: dict, prior: dict, batches: list[dict]) -> dict:
    accepted = _accepted_rows(transcriptions)
    checksum = transcriptions.get("source_checksum")
    if not isinstance(checksum, str):
        raise TypeError("Transkripsiyon kaynak checksum'ı yok")
    if prior.get("schema") != SCHEMA:
        raise ValueError("Önceki tam kalite denetimi gerekli")
    # The original 115-row pre-audit predates the explicit runtime/QLoRA
    # booleans.  It carries no approval and is only accepted as legacy input;
    # the merged artifact always writes both booleans as false.
    _validate_common(prior, checksum, legacy_pre_gate=True)
    allowed = {row["candidate_id"]: row for row in accepted}
    if len(allowed) != len(accepted):
        raise ValueError("Genişletilmiş transkripsiyonda yinelenen aday kimliği var")
    prior_rows = prior.get("candidates", [])
    for row in prior_rows:
        _validate_candidate(row, allowed)
    prior_ids = {row["candidate_id"] for row in prior_rows}
    if len(prior_ids) != len(prior_rows):
        raise ValueError("Önceki kalite denetiminde yinelenen aday kimliği var")
    incremental_ids = set(allowed) - prior_ids
    additions: list[dict] = []
    for batch in batches:
        if batch.get("schema") != BATCH_SCHEMA:
            raise ValueError("Artımlı kalite denetimi şeması geçersiz")
        _validate_common(batch, checksum)
        for row in batch.get("candidates", []):
            _validate_candidate(row, allowed)
            additions.append(row)
    addition_ids = {row["candidate_id"] for row in additions}
    if len(addition_ids) != len(additions) or addition_ids != incremental_ids:
        raise ValueError("Artımlı kalite denetimi yeni OCR adaylarını tam bir kez kapsamalı")
    by_id = {row["candidate_id"]: row for row in [*prior_rows, *additions]}
    rows = [by_id[row["candidate_id"]] for row in accepted]
    return {"schema": SCHEMA, "source_artifacts": {"expanded_transcription": "private"},
            "source_checksum": checksum, "reviewer_kind": "independent_history_agents",
            "is_teacher_approval": False, "answer_key_accessed": False,
            "worked_explanation_accessed": False, "runtime_enabled": False, "qlora_enabled": False,
            "scope": "expanded private AYT OCR quality pre-audit", "summary": _summary(rows),
            "candidates": rows,
            "notice": "Merged agent OCR quality pre-audit. It grants no source approval or runtime/QLoRA access."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--batch-a", type=Path, required=True)
    parser.add_argument("--batch-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    report = merge(load(args.transcriptions), load(args.prior), [load(args.batch_a), load(args.batch_b)])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
