"""Fail-closed hand-off from real-question transcription review to pilot curation.

This script deliberately does *not* create an exam package.  A visual/text
review says only that a transcription matches a source crop; it says nothing
about answer-key provenance, rights, or coaching evidence.  Keeping this
boundary explicit prevents an apparently "reviewed" question from silently
reaching a student-facing API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REVIEW_SCHEMAS = {
    "ogm-ayt-real-question-review-v1",
    "ogm-ayt-real-question-project-owner-review-v1",
}
USAGE_SCHEMA = "ogm-ayt-source-usage-record-v1"
OUTPUT_SCHEMA = "ogm-ayt-real-question-pilot-readiness-v1"
CHECKS = (
    "pdf_text_matches",
    "choices_complete_and_ordered",
    "text_only_accessible",
    "scope_appropriate",
)


def _canonical_checksum(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def usage_template(source_name: str, source_checksum: str) -> dict[str, Any]:
    return {
        "schema": USAGE_SCHEMA,
        "source_name": source_name,
        "source_checksum": source_checksum,
        "scope": "local_pilot_only",
        "basis_kind": "",
        "basis_reference": "",
        "confirmed_by": "",
        "confirmed_at": "",
        "local_pilot_confirmed": False,
        "student_publication_allowed": False,
        "notice": (
            "Bu kayıt, kaynak kullanım dayanağının insan tarafından kontrol edildiğini "
            "belirtmek içindir. Tek başına izin veya yayımlama hakkı oluşturmaz."
        ),
    }


def _valid_usage(usage: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if usage.get("schema") != USAGE_SCHEMA:
        errors.append("kaynak kullanım kaydı şeması geçersiz")
    if usage.get("source_checksum") != review.get("source_checksum"):
        errors.append("kaynak kullanım kaydı checksum'ı inceleme paketiyle uyuşmuyor")
    if usage.get("source_name") != review.get("source_name"):
        errors.append("kaynak kullanım kaydı kaynak adıyla uyuşmuyor")
    if usage.get("scope") != "local_pilot_only":
        errors.append("yalnız local_pilot_only kapsamı kabul edilir")
    if usage.get("basis_kind") not in {"documented_permission", "project_owner_attestation"}:
        errors.append("kaynak kullanım kaydında basis_kind geçersiz")
    if usage.get("student_publication_allowed") is not False:
        errors.append("bu aşamada öğrenci yayını hiçbir zaman açılamaz")
    if usage.get("local_pilot_confirmed") is not True:
        errors.append("yerel pilot kullanım doğrulaması eksik")
    for field in ("basis_reference", "confirmed_by", "confirmed_at"):
        if not isinstance(usage.get(field), str) or len(usage[field].strip()) < 3:
            errors.append(f"kaynak kullanım kaydında {field} eksik")
    return errors


def build(review: dict[str, Any], usage: dict[str, Any]) -> dict[str, Any]:
    if review.get("schema") not in REVIEW_SCHEMAS:
        raise ValueError("gerçek soru inceleme paketi şeması geçersiz")
    rows = review.get("reviews")
    if not isinstance(rows, list) or not rows:
        raise ValueError("inceleme kaydı boş")
    ids = [row.get("id") for row in rows]
    if any(not isinstance(identifier, str) or not identifier for identifier in ids) or len(set(ids)) != len(ids):
        raise ValueError("inceleme kayıt kimlikleri eksik veya yinelenmiş")
    if review.get("review_count") != len(rows):
        raise ValueError("inceleme sayısı kayıtlarla uyuşmuyor")
    usage_errors = _valid_usage(usage, review)
    if usage_errors:
        raise ValueError("; ".join(usage_errors))

    approved: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in rows:
        checks = row.get("checks")
        accepted = isinstance(checks, dict) and all(checks.get(key) is True for key in CHECKS)
        target = approved if accepted else blocked
        target.append({"id": row["id"], "reason": "all_transcription_checks_passed" if accepted else "review_incomplete_or_rejected"})
    return {
        "schema": OUTPUT_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "source_name": review["source_name"],
        "source_checksum": review["source_checksum"],
        "review_artifact_checksum": _canonical_checksum(review),
        "usage_record_checksum": _canonical_checksum(usage),
        "usage_record": {
            "scope": usage["scope"],
            "basis_kind": usage["basis_kind"],
            "basis_reference": usage["basis_reference"],
            "confirmed_by": usage["confirmed_by"],
            "confirmed_at": usage["confirmed_at"],
        },
        "approved_transcription_candidates": approved,
        "blocked_candidates": blocked,
        "answer_key_accessed": False,
        "coaching_evidence_attached": False,
        "runtime_enabled": False,
        "student_exam_enabled": False,
        "next_gate": "answer_key_provenance_and_source_evidence_review",
        "notice": (
            "Bu rapor soru metni doğrulamasının izlenebilir çıktısıdır; deneme paketi değildir. "
            "Cevap anahtarı, kanıt demeti ve ayrı yayın kararı olmadan öğrenciye sunulamaz."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--usage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--write-usage-template", action="store_true")
    args = parser.parse_args()
    review = json.loads(args.review.read_text(encoding="utf-8"))
    if args.write_usage_template:
        args.output.write_text(
            json.dumps(usage_template(review["source_name"], review["source_checksum"]), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return
    usage = json.loads(args.usage.read_text(encoding="utf-8"))
    result = build(review, usage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"approved": len(result["approved_transcription_candidates"]), "runtime_enabled": False}))


if __name__ == "__main__":
    main()
