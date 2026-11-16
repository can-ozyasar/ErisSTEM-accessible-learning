"""Project independently scope-reviewed Dört Dörtlük questions for MEB search.

This projection is discovery-only: the agent review chooses a target section,
but does not approve question quality, evidence, answers, runtime, or training.
Questions with extraction/layout warnings remain outside retrieval until fixed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

OUTPUT_SCHEMA = "ogm-ayt-private-transcription-v1"
TOPIC_BY_SECTION = {
    "1.3": "I. Dünya Savaşı Sürecinde Osmanlı Devleti",
    "2.1": "Millî Mücadele’ye Hazırlık Dönemi",
    "2.4": "Doğu ve Güney Cepheleri ile Bu Cephelerde Öne Çıkan Şahsiyetler",
    "2.5": "Batı Cephesi ve Bu Cephede Öne Çıkan Şahsiyetler",
    "3.1": "Atatürk İlkeleri",
    "3.2": "Siyasi Alandaki Gelişmeler",
}


def build(candidates: dict, review: dict, source_manifest: dict,
          source_manifest_sha256: str) -> dict:
    if candidates.get("schema") != "ogm-dort-dortluk-ayt-target-candidates-v1":
        raise ValueError("Dört Dörtlük kaynak aday şeması geçersiz")
    if review.get("schema") != "independent-ogm-history-teacher-review-v1":
        raise ValueError("Bağımsız tarih ajanı incelemesi gerekli")
    metadata = review.get("review_metadata", {})
    actual_manifest_sha256 = hashlib.sha256(
        json.dumps(source_manifest, ensure_ascii=False, indent=2).encode("utf-8")
    ).hexdigest()
    if (metadata.get("reviewer_kind") != "independent_agent_history_teacher"
            or metadata.get("is_agent_review") is not True
            or metadata.get("is_human_teacher_approval") is not False
            or metadata.get("source_manifest_sha256") != source_manifest_sha256
            or source_manifest.get("schema") != "ogm-dort-dortluk-teacher-review-pack-v1"
            or actual_manifest_sha256 != source_manifest_sha256
            or source_manifest.get("source_checksum") != candidates.get("source_checksum")
            or source_manifest.get("candidate_count") != metadata.get("candidate_count")
            or metadata.get("answer_keys_accessed") is not False
            or metadata.get("worked_solutions_accessed") is not False):
        raise ValueError("Ajan provenance, manifest checksum veya cevap izolasyonu geçersiz")
    if review.get("summary", {}).get("transcription_counts", {}).get("exact") != len(review.get("reviews", [])):
        raise ValueError("Her soru kırpımının metin eşleşmesi incelenmiş olmalı")
    if metadata.get("reviewed_candidate_count") != len(review["reviews"]):
        raise ValueError("Ajan incelemesi tam aday havuzunu kapsamıyor")
    manifest_ids = {row["candidate_id"] for row in source_manifest.get("rows", [])}
    reviewed_ids = {row["candidate_id"] for row in review.get("reviews", [])}
    if (candidates.get("source_checksum") != source_manifest.get("source_checksum")
            or manifest_ids != reviewed_ids):
        raise ValueError("Soru kaynağı checksum'ı eşleşmiyor")

    clean_rows = {row["candidate_id"]: row for row in candidates.get("rows", [])}
    review_rows = {row["candidate_id"] for row in candidates.get("review_queue", [])}
    projected = []
    for verdict in review["reviews"]:
        section = verdict.get("target_section")
        if (verdict.get("coaching_candidate") != "candidate"
                or verdict.get("transcription_match") != "exact"
                or verdict.get("visual_independence") != "text_only"
                or section not in TOPIC_BY_SECTION):
            continue
        candidate_id = verdict["candidate_id"]
        source = clean_rows.get(candidate_id)
        if source is None:
            # Layout/extraction warnings are deliberately sent to repair, not
            # silently promoted from a crop-only scope judgment.
            if candidate_id in review_rows:
                continue
            raise ValueError("Ajan kararı aday manifestinde bulunamadı")
        if (source.get("answer_key_accessed") is not False
                or source.get("worked_explanation_accessed") is not False
                or source.get("source_checksum") != candidates["source_checksum"]):
            raise ValueError("Soru adayı cevap/çözümden yalıtılmış ve checksum bağlı olmalı")
        question = source["question"]
        if question.get("question_type") != "multiple_choice" or question.get("visuals"):
            continue
        projected.append({
            "candidate_id": candidate_id,
            "topic": TOPIC_BY_SECTION[section],
            "question": {
                "stem": " ".join(part.get("text", "").strip()
                                 for part in question.get("parts", []) if part.get("text", "").strip()),
                "choices": [{"label": choice["label"], "text": choice["text"]}
                            for choice in question.get("choices", [])],
            },
            "transcription_status": "private_teacher_review_required",
            "scope_agent_decision": section,
            "scope_agent_reviewed": True,
            "transcription_match": "exact",
            "answer_key_accessed": False,
            "worked_explanation_accessed": False,
        })
    if not projected:
        raise ValueError("Temiz, hedef kapsamlı koçluk adayı yok")
    return {
        "schema": OUTPUT_SCHEMA,
        "source_checksum": candidates["source_checksum"],
        "scope_review": {
            "reviewer_kind": metadata["reviewer_kind"],
            "is_human_teacher_approval": False,
            "source_manifest_sha256": metadata["source_manifest_sha256"],
            "candidate_rows_included": len(projected),
            "review_queue_rows_excluded": sum(
                1 for row in review["reviews"] if row["candidate_id"] in review_rows
                and row.get("coaching_candidate") == "candidate"
            ),
        },
        "rows": projected,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "kaggle_export_enabled": False,
        "qlora_enabled": False,
        "notice": (
            "Private MEB evidence discovery only. Agent scope triage is not teacher approval; "
            "retrieval suggestions require source-PDF crop review and relation validation."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_bytes = args.review_manifest.read_bytes()
    result = build(json.loads(args.candidates.read_text(encoding="utf-8")),
                   json.loads(args.review.read_text(encoding="utf-8")),
                   json.loads(manifest_bytes), hashlib.sha256(manifest_bytes).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"projected_rows": len(result["rows"]),
                      "excluded_layout_candidates": result["scope_review"]["review_queue_rows_excluded"],
                      "runtime_enabled": False, "qlora_enabled": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
