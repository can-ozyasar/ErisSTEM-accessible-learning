"""Make a source-bound, answer-free review pack from a paired behavior run."""
from __future__ import annotations

import argparse
import hashlib
import json
import runpy
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(report: dict, cases: list[dict], *, candidate: str, report_sha256: str, runner_sha256: str) -> dict:
    paired = report.get("paired")
    if report.get("status") != "completed" or not isinstance(paired, dict) or candidate not in paired:
        raise ValueError("tamamlanmış paired davranış raporunda aday bulunamadı")
    results = paired[candidate].get("results")
    if not isinstance(results, list) or len(results) != len(cases):
        raise ValueError("davranış sonucu ve sentetik vaka sayısı eşleşmiyor")
    records = []
    for number, (case, result) in enumerate(zip(cases, results, strict=True), 1):
        response = result.get("reply_preview")
        if not isinstance(response, str) or not response.strip() or len(response) >= 200:
            raise ValueError("kesilmemiş yanıt önizlemesi gerekli")
        if result.get("case") != case.get("case"):
            raise ValueError("davranış sonucu vaka sırası ile eşleşmiyor")
        records.append({
            "id": f"synthetic-{number:02d}", "case": case["case"],
            "question": case["question"], "evidence": case["evidence"],
            "evidence_available": bool(case["evidence"].strip()), "response": response,
        })
    return {
        "schema": "eristem-qlora-synthetic-behavior-review-pack-v1", "candidate": candidate,
        "source_report_sha256": report_sha256, "runner_sha256": runner_sha256,
        "records": records, "answer_key_accessed": False, "student_data_accessed": False,
        "runtime_enabled": False,
        "notice": "Synthetic development review only; not source approval, teacher approval or sealed evaluation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--candidate", choices=("base", "adapter"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    namespace = runpy.run_path(str(args.runner))
    cases = namespace.get("EVAL_CASES")
    if not isinstance(cases, list):
        raise ValueError("runner EVAL_CASES listesini tanımlamıyor")
    payload = build(json.loads(args.report.read_text(encoding="utf-8")), cases, candidate=args.candidate,
                    report_sha256=sha256(args.report), runner_sha256=sha256(args.runner))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"records": len(payload["records"]), "candidate": args.candidate}, ensure_ascii=False))


if __name__ == "__main__":
    main()
