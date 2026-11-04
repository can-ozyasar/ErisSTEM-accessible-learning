"""Fail-closed quality gate between private OCR and evidence retrieval."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED = {"clear", "recoverable_with_crop", "reject_resplit"}


def build(transcriptions: dict, audit: dict) -> tuple[dict, dict]:
    if transcriptions.get("schema") != "ogm-ayt-private-transcription-v1":
        raise ValueError("Private OGM transkripsiyonu gerekli")
    if audit.get("schema") != "ogm-ayt-full-transcription-quality-gate-agent-audit-v1":
        raise ValueError("Tam transkripsiyon kalite kapısı denetimi gerekli")
    if audit.get("source_checksum") != transcriptions.get("source_checksum"):
        raise ValueError("Kalite denetimi ve transkripsiyon checksum'ı eşleşmiyor")
    decisions = audit.get("decisions", audit.get("candidates", audit.get("rows", [])))
    decision_by_id = {row.get("candidate_id"): row for row in decisions}
    source_rows = [row for row in transcriptions.get("rows", [])
                   if row.get("transcription_status") == "private_teacher_review_required"]
    if set(decision_by_id) != {row["candidate_id"] for row in source_rows}:
        raise ValueError("Kalite denetimi OCR-ready satırların tamamını ve yalnız onları içermeli")
    ready, repair, rejected = [], [], []
    for row in source_rows:
        decision = decision_by_id[row["candidate_id"]]
        status = decision.get("transcription_quality", decision.get("transcription_status"))
        if status not in ALLOWED:
            raise ValueError("Geçersiz transkripsiyon kalite kararı")
        if status == "clear":
            ready.append(row)
        elif status == "recoverable_with_crop":
            repair.append({"candidate_id": row["candidate_id"], "topic": row["topic"], "page": row["page"],
                           "reason": decision.get("reason", "crop_repair_required")})
        else:
            rejected.append({"candidate_id": row["candidate_id"], "topic": row["topic"], "page": row["page"],
                             "reason": decision.get("reason", "resplit_required")})
    content = {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": transcriptions["source_checksum"],
               "rows": ready,
               "notice": "Private semantic-gate output. Clear OCR only; source approval remains required before runtime or QLoRA."}
    report = {"schema": "ogm-ayt-semantic-quality-gate-report-v1", "input_ready_count": len(source_rows),
              "clear_count": len(ready), "repair_count": len(repair), "reject_resplit_count": len(rejected),
              "repair_queue": repair, "resplit_queue": rejected,
              "runtime_enabled": False, "qlora_enabled": False}
    return content, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcriptions", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    content, report = build(json.loads(args.transcriptions.read_text(encoding="utf-8")),
                            json.loads(args.audit.read_text(encoding="utf-8")))
    for target, body in ((args.output, content), (args.report_output, report)):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
