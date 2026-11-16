"""Validate and merge blind visual audits of the V10 retrieval delta."""
from __future__ import annotations

import argparse
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

DECISIONS = {"direct", "partial", "irrelevant", "unreadable"}
SUPPORTED_STRATEGIES = {
    "claimwise_option_reserve",
    "claimwise_atom_context_option_reserve",
}
SAFE_FALSE_FLAGS = (
    "answer_key_accessed", "worked_explanation_accessed", "teacher_approval",
    "runtime_enabled", "qlora_enabled", "kaggle_enabled",
)


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _rows_by_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result = {row.get("candidate_id"): row for row in rows}
    if None in result or len(result) != len(rows):
        raise ValueError(f"{label}: eksik veya yinelenen soru kimliği")
    return result


def _audit_partition(pack: dict[str, Any], report: dict[str, Any], queue: dict[str, Any],
                     expected_partition: str) -> tuple[list[dict[str, Any]], list[str]]:
    if pack.get("review_partition") != expected_partition:
        raise ValueError(f"{expected_partition}: paket bölümü uyuşmuyor")
    for source in (pack, report):
        for flag in SAFE_FALSE_FLAGS:
            if source.get(flag) is not False:
                raise ValueError(f"{expected_partition}: {flag}=false olmalı")
    if pack.get("review_scope") != "new_delta_only":
        raise ValueError(f"{expected_partition}: yalnız yeni delta incelenmeli")
    for field in ("source_checksum", "corpus_checksum", "question_source_checksum"):
        if pack.get(field) != report.get(field):
            raise ValueError(f"{expected_partition}: {field} paketle uyuşmuyor")
    if report.get("all_question_source_pages_visually_checked") is not True:
        raise ValueError(f"{expected_partition}: tüm soru sayfaları görsel olarak incelenmeli")
    pack_rows = _rows_by_id(pack.get("reviews", []), f"{expected_partition} paketi")
    report_rows = _rows_by_id(report.get("reviews", []), f"{expected_partition} raporu")
    if set(pack_rows) != set(report_rows):
        raise ValueError(f"{expected_partition}: paket ve rapor soru kümeleri uyuşmuyor")
    if report.get("question_count") != len(pack_rows):
        raise ValueError(f"{expected_partition}: soru sayısı uyuşmuyor")
    if report.get("visually_checked_question_page_count") != len(pack_rows):
        raise ValueError(f"{expected_partition}: kontrol edilen soru sayfası sayısı uyuşmuyor")

    queue_rows = _rows_by_id(queue.get("proposals", []), "retrieval kuyruğu")
    merged_rows: list[dict[str, Any]] = []
    issues: list[str] = []
    checked_total = 0
    for candidate_id, review in sorted(report_rows.items()):
        if candidate_id not in queue_rows:
            raise ValueError(f"{candidate_id}: retrieval kuyruğunda yok")
        pack_row = pack_rows[candidate_id]
        expected_ids = {card["chunk_id"] for card in pack_row.get("new_evidence_cards", [])}
        checked_ids = review.get("visually_checked_chunk_ids")
        if (not isinstance(checked_ids, list) or len(checked_ids) != len(set(checked_ids))
                or set(checked_ids) != expected_ids):
            raise ValueError(f"{candidate_id}: her yeni crop tek tek kontrol edilmeli")
        if review.get("visually_checked_crop_count") != len(expected_ids):
            raise ValueError(f"{candidate_id}: crop kontrol sayısı uyuşmuyor")
        checked_total += len(expected_ids)
        if review.get("visual_independence") != "text_only":
            issues.append(f"{candidate_id}: pilot kapsamı dışı görsel bağımlılık/belirsizlik")
        if review.get("question_source_page_visual_checked") is not True:
            raise ValueError(f"{candidate_id}: orijinal soru sayfası incelenmeli")
        if review.get("question_source_pdf_page") != pack_row.get("question_source_pdf_page"):
            raise ValueError(f"{candidate_id}: soru sayfası provenance uyuşmuyor")

        decision = review.get("delta_decision", review.get("review_decision"))
        if decision not in DECISIONS:
            raise ValueError(f"{candidate_id}: geçersiz delta kararı")
        cards = {card["chunk_id"]: card for card in pack_row.get("new_evidence_cards", [])}
        queue_cards = {card["chunk_id"]: card for card in queue_rows[candidate_id].get("suggestions", [])}
        evidence = review.get("evidence", [])
        if not isinstance(evidence, list) or len(evidence) > 5:
            raise ValueError(f"{candidate_id}: kanıt listesi geçersiz veya beş kaydı aşıyor")
        evidence_ids = []
        for item in evidence:
            chunk_id = item.get("chunk_id")
            evidence_ids.append(chunk_id)
            card = cards.get(chunk_id)
            source_card = queue_cards.get(chunk_id)
            if card is None or source_card is None:
                raise ValueError(f"{candidate_id}: alıntı incelenen delta kuyruğunda yok")
            if (item.get("source_checksum") != card.get("source_checksum")
                    or item.get("page") != card.get("source_page")):
                raise ValueError(f"{candidate_id}: alıntı checksum/sayfa uyuşmuyor")
            quote = str(item.get("quote", "")).strip()
            if not quote:
                raise ValueError(f"{candidate_id}: alıntı boş olamaz: {chunk_id}")
            if _normalize(quote) not in _normalize(str(source_card.get("text", ""))):
                if item.get("quote_visual_verified") is not True:
                    raise ValueError(
                        f"{candidate_id}: OCR metniyle eşleşmeyen alıntı görsel olarak "
                        f"doğrulanmalı: {chunk_id}"
                    )
                issues.append(
                    f"{candidate_id}: {chunk_id} PDF crop'unda görünür alıntı kuyruk metninde "
                    "yok; kaynak metni/koordinat uyumu düzeltilmeden kullanım engelli"
                )
            if not item.get("claim_supported"):
                raise ValueError(f"{candidate_id}: alıntı hangi iddiayı desteklediğini belirtmeli")
        useful_ids = review.get("useful_chunk_ids", review.get("supporting_chunk_ids", []))
        if not isinstance(useful_ids, list) or len(useful_ids) != len(set(useful_ids)):
            raise ValueError(f"{candidate_id}: yararlı kesit kimlikleri geçersiz")
        if not set(useful_ids) <= set(evidence_ids):
            raise ValueError(f"{candidate_id}: yararlı kesitlerin alıntısı eksik")
        if decision == "irrelevant" and useful_ids:
            raise ValueError(f"{candidate_id}: ilgisiz kararda yararlı kanıt işaretlenmiş")
        merged_rows.append({
            "candidate_id": candidate_id,
            "reviewer_partition": expected_partition,
            "delta_decision": decision,
            "visual_independence": review.get("visual_independence"),
            "source_text_alignment_issue": any(
                candidate_id in issue for issue in issues
            ),
            "useful_chunk_ids": useful_ids,
            "evidence": evidence,
            "unsupported_claims": review.get("unsupported_claims", []),
            "reason": review.get("reason", ""),
            "teacher_approval": False,
        })
    if report.get("visually_checked_crop_count") != checked_total:
        raise ValueError(f"{expected_partition}: toplam crop kontrol sayısı uyuşmuyor")
    return merged_rows, issues


def merge(pack_a: dict[str, Any], pack_b: dict[str, Any],
          report_a: dict[str, Any], report_b: dict[str, Any],
          queue: dict[str, Any]) -> dict[str, Any]:
    strategy = queue.get("retrieval_strategy")
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError("Desteklenen seçenek-rezervli retrieval kuyruğu gerekli")
    if pack_a.get("corpus_checksum") != queue.get("corpus_checksum"):
        raise ValueError("V10 paketleri ve retrieval kuyruğu corpus sürümü uyuşmuyor")
    rows_a, issues_a = _audit_partition(pack_a, report_a, queue, "agent-a")
    rows_b, issues_b = _audit_partition(pack_b, report_b, queue, "agent-b")
    ids_a = {row["candidate_id"] for row in rows_a}
    ids_b = {row["candidate_id"] for row in rows_b}
    if ids_a & ids_b:
        raise ValueError("A/B soru kümeleri kesişiyor")
    counts = Counter(row["delta_decision"] for row in [*rows_a, *rows_b])
    return {
        "schema": f"dort-dortluk-{strategy}-delta-review-merged-v1",
        "source_checksum": queue.get("source_checksum"),
        "corpus_checksum": queue.get("corpus_checksum"),
        "retrieval_strategy": queue.get("retrieval_strategy"),
        "question_count": len(rows_a) + len(rows_b),
        "visually_checked_crop_count": sum(
            report.get("visually_checked_crop_count", 0) for report in (report_a, report_b)
        ),
        "delta_decision_counts": dict(sorted(counts.items())),
        "text_only_question_count": sum(
            row["visual_independence"] == "text_only" for row in [*rows_a, *rows_b]
        ),
        "unreadable_crop_count": report_a.get("unreadable_crop_count", 0)
        + report_b.get("unreadable_crop_count", 0),
        "validation_issues": [*issues_a, *issues_b],
        "source_text_alignment_issue_count": len(issues_a) + len(issues_b),
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "teacher_approval": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "kaggle_enabled": False,
        "notice": (
            "Delta-only agent review; these labels do not establish final combined evidence "
            "sufficiency, teacher approval, runtime readiness, or QLoRA eligibility."
        ),
        "reviews": [*rows_a, *rows_b],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack-a", type=Path, required=True)
    parser.add_argument("--pack-b", type=Path, required=True)
    parser.add_argument("--report-a", type=Path, required=True)
    parser.add_argument("--report-b", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = [json.loads(path.read_text(encoding="utf-8")) for path in (
        args.pack_a, args.pack_b, args.report_a, args.report_b, args.queue
    )]
    result = merge(*inputs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "reviews"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
