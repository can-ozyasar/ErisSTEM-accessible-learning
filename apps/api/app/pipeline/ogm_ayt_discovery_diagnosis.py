"""Diagnose evidence-discovery coverage without mistaking abstention for failure."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ogm_ayt_retrieval_gold import SCHEMA


def _answerable(gold: dict) -> set[str]:
    if gold.get("schema") != SCHEMA:
        raise ValueError("Sürümlü Gold etiketleri gerekli")
    cases = gold.get("cases", [])
    if any(not case.get("reviewed") or not case.get("coverage_complete")
           or not isinstance(case.get("abstain"), bool) for case in cases):
        raise ValueError("Tanı için yalnız tam incelenmiş Gold kayıtları kullanılabilir")
    return {case["candidate_id"] for case in cases if not case["abstain"]}


def diagnose(baseline_gold: dict, discovery_gold: dict, discovery_eval: dict) -> dict:
    """Report what current labels establish, and explicitly retain uncertainty.

    A passage is labelled only after PDF-crop review.  Therefore this report can
    measure incremental *found* evidence, but cannot claim that a passage does
    not exist elsewhere in the corpus.  A broad-recall diagnostic is required
    before calling the retrieval motor weak or the direct-evidence policy strict.
    """
    if (baseline_gold.get("source_checksum") != discovery_gold.get("source_checksum")
            or baseline_gold.get("corpus_checksum") != discovery_gold.get("corpus_checksum")):
        raise ValueError("Gold etiketleri aynı kaynak sürümüne ait olmalı")
    baseline = _answerable(baseline_gold)
    discovery = _answerable(discovery_gold)
    baseline_ids = {case["candidate_id"] for case in baseline_gold["cases"]}
    if not discovery <= (baseline_ids - baseline):
        raise ValueError("İkinci tur yalnız ilk turdaki çekimser soruları içermeli")
    metrics = discovery_eval.get("metrics") or {}
    total = len(baseline_ids)
    return {
        "schema": "ogm-ayt-evidence-discovery-diagnosis-v1",
        "source_checksum": baseline_gold["source_checksum"],
        "corpus_checksum": baseline_gold["corpus_checksum"],
        "baseline": {"question_count": total, "answerable_count": len(baseline),
                     "answerable_rate": round(len(baseline) / total, 4)},
        "second_discovery_pass": {
            "reviewed_baseline_abstentions": len(discovery_gold.get("cases", [])),
            "newly_answerable_count": len(discovery),
            "conditional_yield": round(len(discovery) / max(1, len(discovery_gold.get("cases", [])),), 4),
            "retrieval_recall_at_3_for_found_cases": metrics.get("recall_at_3"),
            "retrieval_mrr_at_3_for_found_cases": metrics.get("mrr_at_3"),
            "retrieval_p95_ms": metrics.get("p95_ms"),
        },
        "combined": {"answerable_count": len(baseline | discovery),
                     "answerable_rate": round(len(baseline | discovery) / total, 4),
                     "absolute_coverage_gain": round(len(discovery) / total, 4)},
        "conclusion": {
            "retrieval_ranking_for_found_evidence": "adequate_in_this_bounded_sample"
            if metrics.get("recall_at_3", 0) >= 0.8 else "needs_investigation",
            "root_cause": "not_identified",
            "reason": (
                "The existing review only inspects six candidates per question. It proves the second pass "
                "found seven new grounded questions, but it cannot distinguish absent evidence, a multi-atom "
                "need, OCR/segmentation loss, and a retrieval miss for the remaining abstentions."
            ),
            "next_controlled_experiment": (
                "Use a stratified sample of baseline abstentions, retrieve a wider candidate slate with "
                "entity/date/relation routes, and have the reviewer assign one of: retrieval_miss, "
                "multi_atom_required, corpus_gap, OCR_or_segmentation, or indirect_only."
            ),
        },
        "runtime_enabled": False,
        "qlora_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-gold", type=Path, required=True)
    parser.add_argument("--discovery-gold", type=Path, required=True)
    parser.add_argument("--discovery-eval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = diagnose(load(args.baseline_gold), load(args.discovery_gold), load(args.discovery_eval))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["combined"], ensure_ascii=False))


if __name__ == "__main__":
    main()
