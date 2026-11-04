"""Admit only PDF-crop-checked OCR repairs into a private AYT staging pool."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPAIR_SCHEMA = "ogm-ayt-crop-repair-agent-batch-v1"
OUTPUT_SCHEMA = "ogm-ayt-private-transcription-v1"


def _validate_flags(row: dict) -> None:
    if row.get("source_approval") != "not_granted":
        raise ValueError("Onarılmış OCR satırı kaynak onayı veremez")
    for name in ("runtime_eligible", "qlora_eligible"):
        if row.get(name) is not False:
            raise ValueError(f"{name} false olmalı")


def _validate_question(question: dict) -> None:
    choices = question.get("choices", [])
    if not isinstance(question.get("stem"), str) or len(question["stem"].strip()) < 8:
        raise ValueError("Onarılmış soru kökü yeterli değil")
    if [choice.get("label") for choice in choices] != list("ABCDE"):
        raise ValueError("Onarılmış soru A-E seçeneklerini sırayla içermeli")
    if any(not isinstance(choice.get("text"), str) or not choice["text"].strip() for choice in choices):
        raise ValueError("Onarılmış seçenek metni eksik")
    forbidden = {"answer", "answer_label", "solution", "correct_choice"}
    if forbidden & set(question):
        raise ValueError("Onarılmış soru cevap veya çözüm alanı içeremez")


def build(clear: dict, full_audit: dict, original: dict, batches: list[dict], *, target: int = 120) -> tuple[dict, dict]:
    if clear.get("schema") != OUTPUT_SCHEMA or original.get("schema") != OUTPUT_SCHEMA:
        raise ValueError("Private transkripsiyon girdileri gerekli")
    checksum = original.get("source_checksum")
    if clear.get("source_checksum") != checksum or full_audit.get("source_checksum") != checksum:
        raise ValueError("Onarım girdilerinin kaynak checksum'ları eşleşmiyor")
    original_rows = {row["candidate_id"]: row for row in original.get("rows", [])}
    audit_by_id = {row["candidate_id"]: row for row in full_audit.get("candidates", [])}
    clear_rows = list(clear.get("rows", []))
    if {row["candidate_id"] for row in clear_rows} - set(original_rows):
        raise ValueError("Temiz OCR havuzunda kaynak dışı satır var")
    repaired: dict[str, dict] = {}
    for batch in batches:
        if batch.get("schema") != REPAIR_SCHEMA or batch.get("source_checksum") != checksum:
            raise ValueError("Onarım partisi sürümü veya checksum'ı geçersiz")
        for flag in ("is_teacher_approval", "answer_key_accessed", "worked_explanation_accessed",
                     "runtime_enabled", "qlora_enabled"):
            if batch.get(flag) is not False:
                raise ValueError(f"Onarım partisinde {flag} false olmalı")
        for repair in batch.get("repairs", []):
            candidate_id = repair.get("candidate_id")
            original_row, audit = original_rows.get(candidate_id), audit_by_id.get(candidate_id)
            if original_row is None or audit is None:
                raise ValueError("Onarım kaynağı bilinmiyor")
            if audit.get("transcription_status") != "recoverable_with_crop":
                raise ValueError("Yalnız kırpımla onarılabilir kayıt onarılabilir")
            if repair.get("topic") != original_row.get("topic") or repair.get("page") != original_row.get("page"):
                raise ValueError("Onarım konu veya sayfa bilgisiyle eşleşmiyor")
            _validate_flags(repair)
            status = repair.get("repair_status")
            if status not in {"repaired_clear", "unresolved"}:
                raise ValueError("Onarım sonucu geçersiz")
            if status == "unresolved":
                continue
            if repair.get("pdf_crop_checked") is not True or not repair.get("repair_notes"):
                raise ValueError("Kabul edilen onarım PDF kırpımı ve not gerektirir")
            _validate_question(repair.get("question", {}))
            if repair.get("source") != original_row.get("source"):
                raise ValueError("Onarım kaynak geometrisini değiştiremez")
            if candidate_id in repaired:
                raise ValueError("Aynı OCR adayı iki kez onarılamaz")
            repaired[candidate_id] = {"candidate_id": candidate_id, "topic": repair["topic"], "page": repair["page"],
                                      "question": repair["question"], "source": repair["source"],
                                      "transcription_status": "private_teacher_review_required",
                                      "quality": {"complete_choices": True, "nonempty_stem": True, "nonempty_choices": 5,
                                                  "pdf_crop_repaired": True},
                                      "answer_key_accessed": False, "worked_explanation_accessed": False}
    if len(clear_rows) + len(repaired) < target:
        raise ValueError("Hedef için yeterli PDF-kırpım denetimli OCR onarımı yok")
    rows = [*clear_rows, *(repaired[key] for key in sorted(repaired))][:target]
    if len({row["candidate_id"] for row in rows}) != len(rows):
        raise ValueError("Birleştirilmiş OCR havuzunda yinelenen aday var")
    content = {"schema": OUTPUT_SCHEMA, "source_checksum": checksum, "rows": rows,
               "notice": "Private OCR staging pool only. Crop repair is not teacher source approval; runtime and QLoRA remain disabled."}
    report = {"schema": "ogm-ayt-crop-repair-acceptance-report-v1", "source_checksum": checksum,
              "clear_before_repair": len(clear_rows), "repaired_clear_available": len(repaired),
              "selected_count": len(rows), "target": target, "runtime_enabled": False, "qlora_enabled": False,
              "source_approved_count": 0}
    return content, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", type=Path, required=True)
    parser.add_argument("--full-audit", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--batch-a", type=Path, required=True)
    parser.add_argument("--batch-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--target", type=int, default=120)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    content, report = build(load(args.clear), load(args.full_audit), load(args.original),
                            [load(args.batch_a), load(args.batch_b)], target=args.target)
    for path, body in ((args.output, content), (args.report_output, report)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
