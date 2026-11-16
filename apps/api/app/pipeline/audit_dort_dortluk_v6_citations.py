"""Audit that reviewer option quotes are present in their cited corpus chunks."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u00ad", "").casefold()
    value = re.sub(r"\s+", " ", value)
    return "".join(char for char in value if char.isalnum())


def _corpus_texts(corpus: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for book in corpus.get("books", []):
        index = book.get("index", {})
        for field in ("chunks", "context_chunks", "evidence_atoms"):
            for chunk in index.get(field, []):
                result.setdefault(chunk["id"], []).append({
                    "text": _normalized(chunk.get("text", "")),
                    "source_name": book.get("source_name"),
                    "source_checksum": book.get("source_checksum"),
                    "page": chunk.get("page"),
                })
    return result


def audit(corpus: dict[str, Any], reports: list[tuple[str, dict[str, Any]]],
          legacy_reports: list[tuple[str, dict[str, Any]]] | None = None) -> dict[str, Any]:
    source_texts = _corpus_texts(corpus)
    legacy_meta: dict[tuple[str, str], dict[str, Any]] = {}
    for reviewer, report in legacy_reports or []:
        for row in report.get("reviews", []):
            for card in row.get("card_assessment", []):
                legacy_meta[(row.get("candidate_id", ""), card.get("chunk_id", ""))] = {
                    "source_checksum": card.get("source_checksum"),
                    "page": card.get("page"),
                    "source_name": card.get("source_name"),
                }
    failures: list[dict[str, Any]] = []
    stale_references: list[dict[str, Any]] = []
    checked = 0
    seen_questions: Counter[str] = Counter()
    for reviewer, report in reports:
        for row in report.get("reviews", []):
            candidate_id = row.get("candidate_id", "")
            seen_questions[reviewer] += 1
            options = row.get("options", []) if reviewer == "agent_a" else row.get("option_assessment", [])
            card_fields = (("cards", "new_evidence_cards") if reviewer == "agent_a"
                           else ("card_assessment", "delta_card_assessment"))
            card_meta = {
                card.get("chunk_id"): {
                    "source_checksum": card.get("source_checksum"),
                    "page": card.get("page"),
                    "source_name": card.get("source_name"),
                }
                for field in card_fields for card in row.get(field, [])
                if card.get("chunk_id")
            }
            for option in options:
                verdict = option.get("verdict")
                if verdict not in {"direct", "bounded_inference", "supports"}:
                    continue
                quote = _normalized(option.get("quote", ""))
                ids = option.get("evidence_chunk_ids", [])
                checked += 1
                if not quote:
                    failures.append({
                        "reviewer": reviewer,
                        "candidate_id": candidate_id,
                        "option_label": option.get("label"),
                        "verdict": verdict,
                        "evidence_chunk_ids": ids,
                        "quote_present_in_cited_chunk": False,
                        "reason": "Destek kararı verilmiş seçenekte doğrulanabilir kaynak alıntısı yok.",
                    })
                    continue
                matching_ids = [chunk_id for chunk_id in ids
                                if chunk_id in source_texts
                                and any(quote in item["text"] for item in source_texts[chunk_id])]
                if not matching_ids:
                    quote_hits = [
                        {"chunk_id": chunk_id, **item}
                        for chunk_id, entries in source_texts.items()
                        for item in entries if quote in item["text"]
                    ]
                    expected = next((card_meta[item] for item in ids if item in card_meta), {})
                    if not expected:
                        expected = next((legacy_meta[(candidate_id, item)] for item in ids
                                         if (candidate_id, item) in legacy_meta), {})
                    compatible_hits = [hit for hit in quote_hits
                                       if expected.get("source_checksum") == hit["source_checksum"]
                                       and expected.get("page") == hit["page"]]
                    if compatible_hits:
                        stale_references.append({
                            "reviewer": reviewer,
                            "candidate_id": candidate_id,
                            "option_label": option.get("label"),
                            "old_chunk_ids": ids,
                            "current_chunk_ids": sorted({hit["chunk_id"] for hit in compatible_hits}),
                            "source_checksum": expected.get("source_checksum"),
                            "page": expected.get("page"),
                            "reason": "Alıntı aynı PDF checksum/sayfasında bulundu; referans kimliği yeni corpus sürümünde değişmiş.",
                        })
                    elif quote_hits:
                        failures.append({
                            "reviewer": reviewer, "candidate_id": candidate_id,
                            "option_label": option.get("label"), "verdict": verdict,
                            "evidence_chunk_ids": ids,
                            "global_hits": [{key: hit[key] for key in
                                             ("chunk_id", "source_name", "source_checksum", "page")}
                                            for hit in quote_hits[:5]],
                            "reason": "Alıntı corpus içinde var; ancak gösterilen PDF checksum/sayfa ile uyuşmuyor.",
                        })
                    else:
                        failures.append({
                            "reviewer": reviewer, "candidate_id": candidate_id,
                            "option_label": option.get("label"), "verdict": verdict,
                            "evidence_chunk_ids": ids,
                            "quote_present_in_cited_chunk": False,
                            "reason": "Destekleyici alıntı belirtilen kaynak veya güncel corpus metninde bulunamadı.",
                        })
    return {
        "schema": "dort-dortluk-v6-option-citation-audit-v1",
        "corpus_checksum": corpus.get("corpus_checksum"),
        "review_counts": dict(seen_questions),
        "supporting_option_citations_checked": checked,
        "citation_link_failures": len(failures),
        "failures": failures,
        "stale_chunk_id_references": len(stale_references),
        "stale_reference_rebindings": stale_references,
        "answer_key_accessed": False,
        "teacher_approval": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Bu otomatik alıntı-kaynak bağlantısı kontrolüdür; tarihsel doğruluk veya eğitim onayı değildir. Hata kayıtları PDF crop üzerinden insan/agent incelemesi gerektirir.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--agent-a", type=Path, required=True)
    parser.add_argument("--agent-b", type=Path, required=True)
    parser.add_argument("--v4-agent-a", type=Path, required=True)
    parser.add_argument("--v4-agent-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    reports = [("agent_a", json.loads(args.agent_a.read_text(encoding="utf-8"))),
               ("agent_b", json.loads(args.agent_b.read_text(encoding="utf-8")))]
    legacy_reports = [
        ("agent_a", json.loads(args.v4_agent_a.read_text(encoding="utf-8"))),
        ("agent_b", json.loads(args.v4_agent_b.read_text(encoding="utf-8"))),
    ]
    result = audit(corpus, reports, legacy_reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "review_counts", "supporting_option_citations_checked", "citation_link_failures",
        "stale_chunk_id_references",
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
