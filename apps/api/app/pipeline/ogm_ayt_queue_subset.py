"""Create a reproducible private retrieval queue subset from reviewed Gold labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ogm_ayt_retrieval_gold import QUEUE_SCHEMAS, SCHEMA


def baseline_abstentions(queue: dict, gold: dict) -> dict:
    """Keep only questions that a prior complete review marked as unsupported.

    This prevents a second discovery pass from being credited for questions that
    were already answerable in the baseline.  The returned queue preserves its
    source and corpus checksums, so it remains invalid if either source changes.
    """
    if queue.get("schema") not in QUEUE_SCHEMAS or gold.get("schema") != SCHEMA:
        raise ValueError("Sürümlü kanıt kuyruğu ve Gold etiketleri gerekli")
    if (queue.get("source_checksum") != gold.get("source_checksum")
            or queue.get("corpus_checksum") != gold.get("corpus_checksum")):
        raise ValueError("Kuyruk ve Gold kaynak sürümleri eşleşmiyor")
    cases = gold.get("cases", [])
    if any(not case.get("reviewed") or not case.get("coverage_complete")
           or not isinstance(case.get("abstain"), bool) for case in cases):
        raise ValueError("Yalnız tam incelenmiş Gold etiketleriyle alt küme oluşturulabilir")
    abstained_ids = {case["candidate_id"] for case in cases if case["abstain"]}
    proposals = queue.get("proposals", [])
    proposal_ids = {row.get("candidate_id") for row in proposals}
    if not abstained_ids <= proposal_ids:
        raise ValueError("Gold çekimser soru kümesi kuyrukta eksik")
    return {
        **queue,
        "proposals": [row for row in proposals if row["candidate_id"] in abstained_ids],
        "subset_of_gold": "baseline_abstentions",
        "baseline_gold_case_count": len(cases),
        "notice": "Private diagnostic subset. It is not runtime evidence or QLoRA data.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    output = baseline_abstentions(load(args.queue), load(args.gold))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"proposal_count": len(output["proposals"])}))


if __name__ == "__main__":
    main()
