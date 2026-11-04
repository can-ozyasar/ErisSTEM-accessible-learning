"""Private, teacher-reviewed retrieval labels for the OGM AYT pilot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..history_rag_hybrid import evaluate_rankings

SCHEMA = "ogm-ayt-retrieval-gold-v1"


def source_key(item: dict) -> str:
    return f'{item["source_checksum"]}:{item["chunk_id"]}'


def build_template(queue: dict) -> dict:
    if queue.get("schema") != "ogm-ayt-evidence-review-queue-v3":
        raise ValueError("Sürümlü OGM kanıt öneri kuyruğu gerekli")
    return {
        "schema": SCHEMA, "source_checksum": queue["source_checksum"],
        "corpus_checksum": queue["corpus_checksum"],
        "cases": [{
            "candidate_id": row["candidate_id"],
            "reviewed": False, "crop_checked": False, "coverage_complete": False,
            "reviewer": None, "abstain": None,
            # A teacher can add a source outside top-k after a PDF search.
            # Otherwise a missed gold source would be impossible to label.
            "judgments": [{"source_key": source_key(item), "verdict": "pending"}
                          for item in row.get("suggestions", [])],
        } for row in queue.get("proposals", [])],
        "runtime_enabled": False, "qlora_enabled": False,
        "notice": "Private label template; candidate passages are not approved evidence.",
    }


def evaluate(queue: dict, gold: dict, corpus: dict) -> dict:
    if queue.get("schema") != "ogm-ayt-evidence-review-queue-v3" or gold.get("schema") != SCHEMA:
        raise ValueError("Altın değerlendirme şeması geçersiz")
    if (gold.get("source_checksum") != queue.get("source_checksum")
            or gold.get("corpus_checksum") != queue.get("corpus_checksum")
            or corpus.get("corpus_checksum") != queue.get("corpus_checksum")):
        raise ValueError("Soru veya MEB kaynak sürümü değişmiş")
    known = {f'{book["source_checksum"]}:{chunk["id"]}'
             for book in corpus.get("books", []) for chunk in book.get("index", {}).get("chunks", [])}
    proposal_by_id = {row["candidate_id"]: row for row in queue.get("proposals", [])}
    cases = gold.get("cases", [])
    if len(cases) != len(proposal_by_id) or {case.get("candidate_id") for case in cases} != set(proposal_by_id):
        raise ValueError("Altın değerlendirme tüm soru gruplarını içermeli")
    labels, rankings, latencies = [], {}, []
    for case in cases:
        if not case.get("reviewed"):
            continue
        if not case.get("crop_checked") or not case.get("coverage_complete") or not case.get("reviewer"):
            raise ValueError("PDF kırpımı, kapsam taraması ve inceleyen gerekli")
        judged = case.get("judgments", [])
        keys = [item.get("source_key") for item in judged]
        if len(set(keys)) != len(keys) or any(item.get("verdict") not in {"support", "wrong"} for item in judged):
            raise ValueError("Kaynak kararları tamamlanmış ve tekil olmalı")
        if not set(keys) <= known:
            raise ValueError("Altın kanıt güncel MEB corpus'unda bulunmalı")
        support = [item["source_key"] for item in judged if item["verdict"] == "support"]
        wrong = [item["source_key"] for item in judged if item["verdict"] == "wrong"]
        abstain = case.get("abstain")
        if not isinstance(abstain, bool) or (abstain and support) or (not abstain and not support):
            raise ValueError("Yanıtlanabilirlik ve altın kanıt etiketleri çelişiyor")
        row = proposal_by_id[case["candidate_id"]]
        labels.append({"id": case["candidate_id"], "gold_source_ids": support,
                       "wrong_source_ids": wrong, "abstain": abstain})
        rankings[case["candidate_id"]] = [source_key(item) for item in row.get("suggestions", [])]
        latencies.append(row.get("retrieval_ms", 0))
    if not labels:
        return {"schema": "ogm-ayt-retrieval-eval-v1", "reviewed_count": 0,
                "pending_count": len(cases), "metrics": None, "runtime_enabled": False}
    metrics = evaluate_rankings(labels, rankings, latencies)
    return {"schema": "ogm-ayt-retrieval-eval-v1", "reviewed_count": len(labels),
            "pending_count": len(cases) - len(labels), "metrics": metrics,
            "runtime_enabled": False,
            "notice": "Private development review; no source approval or model acceptance implied."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("template", "evaluate"))
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--gold", type=Path)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    if args.command == "evaluate" and (args.gold is None or args.corpus is None):
        parser.error("--gold ve --corpus değerlendirme için gerekli")
    body = (build_template(queue) if args.command == "template" else
            evaluate(queue, json.loads(args.gold.read_text(encoding="utf-8")),
                     json.loads(args.corpus.read_text(encoding="utf-8"))))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
