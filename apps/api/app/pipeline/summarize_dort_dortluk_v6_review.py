"""Merge split V4/V6 Dört Dörtlük reviews into a reproducible private summary."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DECISIONS = {"direct", "bounded_inference", "insufficient", "wrong"}


def _indexed(report: dict[str, Any], *, version: str) -> dict[str, tuple[str, str]]:
    rows = report.get("reviews")
    if not isinstance(rows, list):
        raise TypeError(f"{version} raporunda reviews listesi gerekli")
    indexed: dict[str, tuple[str, str]] = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        if version in {"v4-agent-a", "v6-agent-a"}:
            decision_key = "question_decision" if version == "v4-agent-a" else "final_decision"
            decision = row.get(decision_key)
        else:
            decision = row.get("bundle_assessment", {}).get("decision")
        if not candidate_id or decision not in DECISIONS:
            raise ValueError(f"{version} geçersiz karar/kayıt içeriyor")
        if candidate_id in indexed:
            raise ValueError(f"{version} yinelenen aday: {candidate_id}")
        indexed[candidate_id] = (decision, str(row.get("topic", "Bilinmeyen ünite")))
    return indexed


def summarize(a_v4: dict[str, Any], b_v4: dict[str, Any],
              a_v6: dict[str, Any], b_v6: dict[str, Any],
              adjudications: dict[str, Any] | None = None) -> dict[str, Any]:
    for name, report in (("V4 A", a_v4), ("V4 B", b_v4), ("V6 A", a_v6), ("V6 B", b_v6)):
        if report.get("answer_key_accessed") is not False:
            raise ValueError(f"{name}: cevap anahtarı erişim bayrağı false olmalı")
        for flag in ("runtime_enabled", "qlora_enabled"):
            if report.get(flag) is True:
                raise ValueError(f"{name}: {flag} kapalı olmalı")

    old_a = _indexed(a_v4, version="v4-agent-a")
    old_b = _indexed(b_v4, version="v4-agent-b")
    new_a = _indexed(a_v6, version="v6-agent-a")
    new_b = _indexed(b_v6, version="v6-agent-b")
    if any(len(part) != 64 for part in (old_a, old_b, new_a, new_b)):
        raise ValueError("Her bağımsız rapor tam 64 soruyu kapsamalı")
    if (set(old_a) & set(old_b) or set(new_a) & set(new_b)
            or set(old_a) | set(old_b) != set(new_a) | set(new_b)):
        raise ValueError("V4/V6 review kümeleri aynı 128 soruyu tam bir kez kapsamalı")

    old = {**old_a, **old_b}
    new = {**new_a, **new_b}
    applied_adjudications: list[dict[str, str]] = []
    adjudication_rows = (adjudications or {}).get("adjudications", [])
    if adjudications is not None:
        if adjudications.get("answer_key_accessed") is not False:
            raise ValueError("Adjudication cevap anahtarından bağımsız olmalı")
        if any(adjudications.get(flag) is True for flag in
               ("runtime_enabled", "qlora_enabled", "teacher_approval")):
            raise ValueError("Adjudication onay/runtime/eğitim kapılarını açamaz")
    seen_adjudications: set[str] = set()
    for item in adjudication_rows:
        cid, decision = item.get("candidate_id"), item.get("decision")
        if (cid not in new or cid in seen_adjudications
                or decision not in DECISIONS or not item.get("reason")):
            raise ValueError("Adjudication kaydı geçersiz veya V6 dışı")
        seen_adjudications.add(cid)
        previous, topic = new[cid]
        new[cid] = (decision, topic)
        applied_adjudications.append({
            "candidate_id": cid, "from": previous, "to": decision,
            "status": str(item.get("question_integrity", "reviewed")),
            "reason": str(item["reason"]),
        })
    old_counts = Counter(item[0] for item in old.values())
    new_counts = Counter(item[0] for item in new.values())
    per_topic: dict[str, dict[str, int]] = defaultdict(dict)
    for decision, topic in new.values():
        per_topic[topic][decision] = per_topic[topic].get(decision, 0) + 1

    changed = [
        {"candidate_id": cid, "from": old[cid][0], "to": new[cid][0]}
        for cid in sorted(new) if old[cid][0] != new[cid][0]
    ]
    old_supported = old_counts["direct"] + old_counts["bounded_inference"]
    new_supported = new_counts["direct"] + new_counts["bounded_inference"]
    return {
        "schema": "dort-dortluk-v6-review-merged-summary-v1",
        "review_count": len(new),
        "v4_decision_counts": dict(sorted(old_counts.items())),
        "v6_decision_counts": dict(sorted(new_counts.items())),
        "supported_bundle_count": new_supported,
        "supported_bundle_delta": new_supported - old_supported,
        "changed_decision_count": len(changed),
        "changed_decisions": changed,
        "adjudications_applied": applied_adjudications,
        "v6_counts_by_topic": {key: dict(sorted(value.items()))
                                for key, value in sorted(per_topic.items())},
        "reviewer_reports": {"v6_a": a_v6.get("review_count"),
                             "v6_b": b_v6.get("review_count")},
        "answer_key_accessed": False,
        "teacher_approval": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "kaggle_enabled": False,
        "notice": "Agent kaynak denetimi ve V4 karşılaştırmasıdır; öğretmen onayı veya eğitim kapısı değildir.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v4-a", type=Path, required=True)
    parser.add_argument("--v4-b", type=Path, required=True)
    parser.add_argument("--v6-a", type=Path, required=True)
    parser.add_argument("--v6-b", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in
               (args.v4_a, args.v4_b, args.v6_a, args.v6_b)]
    adjudications = (json.loads(args.adjudications.read_text(encoding="utf-8"))
                     if args.adjudications else None)
    result = summarize(*reports, adjudications=adjudications)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "review_count", "v4_decision_counts", "v6_decision_counts",
        "supported_bundle_count", "supported_bundle_delta", "changed_decision_count",
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
