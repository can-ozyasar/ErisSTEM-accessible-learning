"""Audit and merge blind V7 top-24 evidence reviews without opening answer keys."""
from __future__ import annotations

import argparse
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

DECISIONS = {"direct", "bounded_inference", "insufficient", "wrong"}
VISUAL_DECISIONS = {"text_only", "visual_dependent", "unclear"}
# Evidence review can require one citation per distinct relation in a matching
# question. Keep the diagnostic bundle bounded, but do not impose the narrower
# QLoRA export limit on source adequacy review.
MAX_REVIEW_EVIDENCE_ATOMS = 5


def _normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _index_pack(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if pack.get("answer_key_accessed") is not False:
        raise ValueError("İnceleme paketi cevap anahtarından bağımsız olmalı")
    if pack.get("teacher_approval") is not False:
        raise ValueError("Ajan paketi öğretmen onayı sayılmaz")
    if pack.get("runtime_enabled") is not False or pack.get("qlora_enabled") is not False:
        raise ValueError("Review paketi runtime/QLoRA açamaz")
    if "kaggle_enabled" in pack and pack.get("kaggle_enabled") is not False:
        raise ValueError("Review paketi Kaggle'a veri aktaramaz")
    rows = pack.get("reviews")
    if not isinstance(rows, list):
        raise TypeError("Pakette reviews listesi gerekli")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        if not candidate_id or candidate_id in indexed:
            raise ValueError("Pakette aday kimliği eksik veya yineleniyor")
        indexed[candidate_id] = row
    if pack.get("question_count") != len(indexed):
        raise ValueError("Paket soru sayısı manifestle eşleşmiyor")
    return indexed


def _index_report(report: dict[str, Any], *, name: str) -> dict[str, dict[str, Any]]:
    for flag in ("answer_key_accessed", "worked_explanation_accessed",
                 "teacher_approval", "runtime_enabled", "qlora_enabled", "kaggle_enabled"):
        if report.get(flag) is not False:
            raise ValueError(f"{name}: {flag}=false olmalı")
    all_crops_checked = report.get(
        "all_review_crops_visually_checked",
        report.get("all_new_crops_visually_checked"),
    )
    if all_crops_checked is not True:
        raise ValueError(f"{name}: paketteki bütün kırpımlar görsel kontrol edilmeli")
    rows = report.get("reviews")
    if not isinstance(rows, list):
        raise TypeError(f"{name}: reviews listesi gerekli")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        if not candidate_id or candidate_id in indexed:
            raise ValueError(f"{name}: eksik veya yinelenen soru kimliği")
        if row.get("final_decision") not in DECISIONS:
            raise ValueError(f"{name}: geçersiz kanıt kararı: {candidate_id}")
        if row.get("visual_independence") not in VISUAL_DECISIONS:
            raise ValueError(f"{name}: geçersiz görsel kapsam kararı: {candidate_id}")
        indexed[candidate_id] = row
    if report.get("review_count") != len(indexed):
        raise ValueError(f"{name}: review_count uyuşmuyor")
    return indexed


def _audit_row(review: dict[str, Any], pack_row: dict[str, Any],
               queue_row: dict[str, Any], candidate_id: str) -> list[dict[str, str]]:
    cards = {card["chunk_id"]: card for card in pack_row.get("new_evidence_cards", [])}
    queue_cards = {card["chunk_id"]: card for card in queue_row.get("suggestions", [])}
    evidence = review.get("evidence", [])
    if not isinstance(evidence, list):
        raise TypeError(f"{candidate_id}: evidence liste olmalı")
    if len(evidence) > MAX_REVIEW_EVIDENCE_ATOMS:
        raise ValueError(
            f"{candidate_id}: raporda en fazla {MAX_REVIEW_EVIDENCE_ATOMS} "
            "alıntılı kaynak tutulabilir")
    ids = review.get("supporting_chunk_ids", [])
    if (not isinstance(ids, list) or len(ids) > MAX_REVIEW_EVIDENCE_ATOMS
            or len(ids) != len(set(ids))):
        raise ValueError(
            f"{candidate_id}: en fazla {MAX_REVIEW_EVIDENCE_ATOMS} "
            "benzersiz kaynak kimliği kullanılabilir")
    decision = review["final_decision"]
    evidence_ids = [item.get("chunk_id") for item in evidence]
    if decision in {"direct", "bounded_inference"} and (
        not evidence or set(ids) != set(evidence_ids)
    ):
        raise ValueError(f"{candidate_id}: olumlu kararda alıntılı kanıt zorunlu")
    if decision in {"insufficient", "wrong"} and not set(ids) <= set(evidence_ids):
        raise ValueError(f"{candidate_id}: destek ID'si alıntı kayıtlarında bulunmuyor")
    problems: list[dict[str, str]] = []
    for item in evidence:
        chunk_id = item.get("chunk_id")
        card = cards.get(chunk_id)
        if card is None:
            problems.append({"candidate_id": candidate_id, "chunk_id": str(chunk_id),
                             "problem": "citation_not_in_reviewed_pack"})
            continue
        if (item.get("source_checksum") != card.get("source_checksum")
                or item.get("page") != card.get("source_page")):
            problems.append({"candidate_id": candidate_id, "chunk_id": chunk_id,
                             "problem": "citation_source_mismatch"})
        quote = str(item.get("quote", "")).strip()
        queue_card = queue_cards.get(chunk_id)
        if queue_card is None:
            problems.append({"candidate_id": candidate_id, "chunk_id": str(chunk_id),
                             "problem": "chunk_not_in_v7_queue"})
            continue
        if (queue_card.get("source_checksum") != card.get("source_checksum")
                or queue_card.get("page") != card.get("source_page")):
            problems.append({"candidate_id": candidate_id, "chunk_id": chunk_id,
                             "problem": "pack_queue_provenance_mismatch"})
        source_text = str(queue_card.get("text", ""))
        if not quote or not source_text or _normalized(quote) not in _normalized(source_text):
            problems.append({"candidate_id": candidate_id, "chunk_id": chunk_id,
                             "problem": "quote_not_exact_substring_of_candidate"})
        if not item.get("claim_supported"):
            problems.append({"candidate_id": candidate_id, "chunk_id": chunk_id,
                             "problem": "claim_supported_empty"})
    if decision in {"direct", "bounded_inference"} and problems:
        raise ValueError(f"{candidate_id}: olumlu kararın provenance/alinti kontrolü başarısız")
    return problems


def merge(pack_a: dict[str, Any], pack_b: dict[str, Any],
          report_a: dict[str, Any], report_b: dict[str, Any],
          v7_queue: dict[str, Any], *, expected_question_count: int = 89,
          expected_crops_per_question: int = 12,
          result_schema: str = "dort-dortluk-v7-top24-review-merged-v1") -> dict[str, Any]:
    pack_indexes = {
        "agent-a": _index_pack(pack_a),
        "agent-b": _index_pack(pack_b),
    }
    review_indexes = {
        "agent-a": _index_report(report_a, name="agent-a"),
        "agent-b": _index_report(report_b, name="agent-b"),
    }
    for name, pack, report in (
        ("agent-a", pack_a, report_a), ("agent-b", pack_b, report_b),
    ):
        for checksum_field in ("source_checksum", "corpus_checksum"):
            if (not pack.get(checksum_field)
                    or report.get(checksum_field) != pack.get(checksum_field)):
                raise ValueError(f"{name}: {checksum_field} paket sürümüyle eşleşmiyor")
        if pack.get("question_source_checksum"):
            if pack.get("question_source_checksum") != v7_queue.get("source_checksum"):
                raise ValueError(f"{name}: soru PDF checksum'ı transkripsiyonla uyuşmuyor")
            if report.get("question_source_checksum") != pack.get("question_source_checksum"):
                raise ValueError(f"{name}: inceleme raporu soru PDF checksum'ını doğrulamıyor")
            if report.get("all_question_source_pages_visually_checked") is not True:
                raise ValueError(f"{name}: orijinal soru sayfaları görsel olarak kontrol edilmeli")
            question_count = len(pack.get("reviews", []))
            if report.get("visually_checked_question_page_count") != question_count:
                raise ValueError(f"{name}: görsel kontrol edilen soru sayfası sayısı uyuşmuyor")
            expected_crop_count = question_count * expected_crops_per_question
            if report.get("visually_checked_crop_count") != expected_crop_count:
                raise ValueError(f"{name}: görsel kontrol edilen kanıt kırpımı sayısı uyuşmuyor")
    queue_rows = {row["candidate_id"]: row for row in v7_queue.get("proposals", [])}
    all_ids: set[str] = set()
    final_rows: list[dict[str, Any]] = []
    citation_issues: list[dict[str, str]] = []
    decisions: Counter[str] = Counter()
    visual: Counter[str] = Counter()
    insufficient_candidates: Counter[str] = Counter()
    for name in ("agent-a", "agent-b"):
        pack, report = pack_indexes[name], review_indexes[name]
        if set(pack) != set(report):
            raise ValueError(f"{name}: rapor ve inceleme paketi soru kümeleri uyuşmuyor")
        if all_ids & set(pack):
            raise ValueError("A/B inceleme kümeleri kesişiyor")
        all_ids |= set(pack)
        for candidate_id, review in sorted(report.items()):
            if candidate_id not in queue_rows:
                raise ValueError(f"V7 retrieval kuyruğunda olmayan soru: {candidate_id}")
            expected_visual_ids = {
                card["chunk_id"] for card in pack[candidate_id].get("new_evidence_cards", [])
            }
            checked_visual_ids = review.get("visually_checked_chunk_ids")
            if (len(expected_visual_ids) != expected_crops_per_question
                    or not isinstance(checked_visual_ids, list)
                    or len(checked_visual_ids) != len(set(checked_visual_ids))
                    or set(checked_visual_ids) != expected_visual_ids):
                raise ValueError(
                    f"{candidate_id}: her yeni PDF kırpımı görsel olarak tek tek doğrulanmalı")
            relevant_ids = review.get("relevant_chunk_ids")
            irrelevant_ids = review.get("irrelevant_chunk_ids")
            if relevant_ids is not None or irrelevant_ids is not None:
                if not isinstance(relevant_ids, list) or not isinstance(irrelevant_ids, list):
                    raise ValueError(f"{candidate_id}: ilgili/ilgisiz kesit listeleri gerekli")
                relevant_set, irrelevant_set = set(relevant_ids), set(irrelevant_ids)
                if (len(relevant_set) != len(relevant_ids)
                        or len(irrelevant_set) != len(irrelevant_ids)
                        or relevant_set & irrelevant_set
                        or relevant_set | irrelevant_set != expected_visual_ids):
                    raise ValueError(
                        f"{candidate_id}: ilgili ve ilgisiz listeleri tüm slate'i "
                        "çakışmasız biçimde kapsamalı")
                if review["final_decision"] == "insufficient":
                    label = ("relevant_candidates_but_insufficient"
                             if relevant_set else "no_relevant_candidate_in_reviewed_slate")
                    insufficient_candidates[label] += 1
            if pack[candidate_id].get("question_source_page_image"):
                if review.get("question_source_page_visual_checked") is not True:
                    raise ValueError(f"{candidate_id}: orijinal soru sayfası görseli incelenmeli")
                if (review.get("question_source_pdf_page")
                        != pack[candidate_id].get("question_source_pdf_page")):
                    raise ValueError(f"{candidate_id}: orijinal soru sayfası provenance uyuşmuyor")
            citation_issues.extend(_audit_row(
                review, pack[candidate_id], queue_rows[candidate_id], candidate_id))
            decisions[review["final_decision"]] += 1
            visual[review["visual_independence"]] += 1
            final_rows.append({
                "candidate_id": candidate_id,
                "reviewer_partition": name,
                "final_decision": review["final_decision"],
                "visual_independence": review["visual_independence"],
                "visual_scope_reason": review.get("visual_scope_reason", ""),
                "relevant_chunk_ids": review.get("relevant_chunk_ids", []),
                "irrelevant_chunk_ids": review.get("irrelevant_chunk_ids", []),
                "supporting_chunk_ids": review.get("supporting_chunk_ids", []),
                "evidence": review.get("evidence", []),
                "unsupported_claims": review.get("unsupported_claims", []),
                "reason": review.get("reason", ""),
                "teacher_approval": False,
            })
    if len(all_ids) != expected_question_count:
        raise ValueError(
            f"İnceleme raporu {expected_question_count} soru grubunu tam kapsamalı; "
            f"bulundu: {len(all_ids)}")
    supported = sum(decisions[decision] for decision in ("direct", "bounded_inference"))
    text_supported = sum(
        row["final_decision"] in {"direct", "bounded_inference"}
        and row["visual_independence"] == "text_only"
        for row in final_rows
    )
    return {
        "schema": result_schema,
        "review_count": len(final_rows),
        "decision_counts": dict(sorted(decisions.items())),
        "visual_scope_counts": dict(sorted(visual.items())),
        "insufficient_candidate_diagnostic_counts": dict(
            sorted(insufficient_candidates.items())),
        "supported_candidate_count": supported,
        "text_only_supported_candidate_count": text_supported,
        "citation_issue_count": len(citation_issues),
        "citation_issues": citation_issues,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "teacher_approval": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "kaggle_enabled": False,
        "reviews": final_rows,
        "notice": "Yeni adayların kör agent kanıt denetimidir; öğretmen onayı, bağımsız kapalı test veya eğitim izni değildir.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("pack-a", "pack-b", "report-a", "report-b", "v7"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-question-count", type=int, default=89)
    parser.add_argument("--expected-crops-per-question", type=int, default=12)
    parser.add_argument("--result-schema", default="dort-dortluk-v7-top24-review-merged-v1")
    args = parser.parse_args()
    def load(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))
    result = merge(load(args.pack_a / "manifest.json"), load(args.pack_b / "manifest.json"),
                   load(args.report_a), load(args.report_b), load(args.v7),
                   expected_question_count=args.expected_question_count,
                   expected_crops_per_question=args.expected_crops_per_question,
                   result_schema=args.result_schema)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "review_count", "decision_counts", "visual_scope_counts",
        "supported_candidate_count", "text_only_supported_candidate_count",
        "citation_issue_count",
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
