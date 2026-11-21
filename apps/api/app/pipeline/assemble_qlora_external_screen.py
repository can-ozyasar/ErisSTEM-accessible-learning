"""Bind an external synthetic review to paired-run outputs without inventing latency."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(pack: dict, review: dict, paired_report: dict) -> dict:
    if pack.get("schema") != "eristem-qlora-synthetic-behavior-review-pack-v1":
        raise ValueError("sentetik davranış inceleme paketi gerekli")
    candidate = pack.get("candidate")
    if review.get("schema") != "deepseek-qlora-synthetic-output-review-v1" or review.get("candidate") != candidate:
        raise ValueError("harici inceleme paketi adayla eşleşmiyor")
    if review.get("source_report_sha256") != pack.get("source_report_sha256"):
        raise ValueError("harici inceleme farklı davranış raporuna bağlı")
    results = paired_report.get("paired", {}).get(candidate, {}).get("results")
    if paired_report.get("status") != "completed" or not isinstance(results, list) or len(results) != len(pack.get("records", [])):
        raise ValueError("paired model çıktıları eksik")
    labels = {item.get("id"): item for item in review.get("reviews", []) if isinstance(item, dict)}
    if set(labels) != {item.get("id") for item in pack["records"]}:
        raise ValueError("harici inceleme her kaydı tam kapsamıyor")
    records = []
    for item, generated in zip(pack["records"], results, strict=True):
        label = labels[item["id"]]
        if generated.get("case") != item["case"] or generated.get("reply_preview") != item["response"]:
            raise ValueError("paired çıktı inceleme paketiyle uyuşmuyor")
        full_ms = generated.get("seconds")
        if not isinstance(full_ms, (int, float)) or full_ms < 0:
            raise ValueError("tam yanıt süresi eksik")
        records.append({"id": item["id"], "case": item["case"], "response": item["response"],
                        "evidence_available": item["evidence_available"],
                        "source_external_claim": label["source_external_claim"],
                        "wrong_source_attribution": label["wrong_source_attribution"],
                        "first_token_ms": None, "full_response_ms": round(float(full_ms) * 1000, 3)})
    return {"schema": "eristem-tutor-qlora-predictions-v1", "candidate": candidate, "split": "dev",
            "input_manifest_sha256": pack["source_report_sha256"], "semantic_label_provenance": "external_ai_screen",
            "records": records, "notice": "Synthetic external screen; no first-token measurement, no human approval, no sealed evaluation."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True); parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--paired-report", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.pack.read_text(encoding="utf-8")), json.loads(args.review.read_text(encoding="utf-8")),
                   json.loads(args.paired_report.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"records": len(result["records"]), "candidate": result["candidate"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
