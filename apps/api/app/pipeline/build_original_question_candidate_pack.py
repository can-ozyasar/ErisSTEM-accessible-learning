"""Select a balanced, private 120-question candidate pack from reviewed drafts."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path

from ..question_scope import visual_dependency_reasons

LABELS = "ABCDE"
SCHEMA = "ayt-history-original-question-candidate-pack-v1"


def _round_robin_by_section(rows: list[dict], count: int) -> list[dict]:
    buckets: dict[tuple[int, str], deque[dict]] = defaultdict(deque)
    for row in sorted(rows, key=lambda item: (item["source_evidence"]["grade"], item["source_evidence"]["section_id"], item["id"])):
        source = row["source_evidence"]
        buckets[(source["grade"], source["section_id"])].append(row)
    keys = deque(sorted(buckets))
    selected = []
    while keys and len(selected) < count:
        key = keys.popleft()
        selected.append(buckets[key].popleft())
        if buckets[key]:
            keys.append(key)
    if len(selected) != count:
        raise ValueError("Dengeli seçim için yeterli taslak yok")
    return selected


def build(gates: list[dict], *, target_count: int = 120, exclude_ids: set[str] | None = None) -> dict:
    if target_count != 120:
        raise ValueError("İlk aday paketinin hedefi tam 120 soru olmalı")
    corpus_checksum = None
    exclude_ids = exclude_ids or set()
    records: list[dict] = []
    seen = set()
    for gate in gates:
        if gate.get("schema") != "ayt-history-original-question-review-gate-v1":
            raise ValueError("Bağımsız soru inceleme kapısı gerekli")
        if corpus_checksum is None:
            corpus_checksum = gate.get("corpus_checksum")
        elif corpus_checksum != gate.get("corpus_checksum"):
            raise ValueError("Aday kapılarının corpus checksum değerleri uyuşmuyor")
        for item in gate.get("accepted_for_source_crop_validation", []):
            draft = item.get("draft", {})
            identifier = draft.get("id")
            if (not identifier or identifier in seen or item.get("source_crop_validation_required") is not True
                    or item.get("runtime_enabled") is not False
                    or item.get("independent_review", {}).get("verdict") != "accept_for_source_validation"):
                raise ValueError("Aday taslak sözleşmesi geçersiz")
            if visual_dependency_reasons({"stem": draft.get("question", ""), "choices": draft.get("choices", [])}):
                raise ValueError("Görsel bağımlı taslak aday paketine giremez")
            seen.add(identifier)
            if identifier not in exclude_ids:
                records.append(draft)
    per_label = target_count // len(LABELS)
    grouped = {label: [row for row in records if row.get("correct_label") == label] for label in LABELS}
    if any(len(grouped[label]) < per_label for label in LABELS):
        raise ValueError("Dengeli cevap anahtarı için yeterli kabul edilmiş taslak yok")
    selected = [row for label in LABELS for row in _round_robin_by_section(grouped[label], per_label)]
    selected.sort(key=lambda row: int(row["id"].rsplit("-", 1)[-1]))
    candidate_checksum = hashlib.sha256(json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"schema": SCHEMA, "corpus_checksum": corpus_checksum, "candidate_checksum": candidate_checksum,
            "questions": [{**row, "status": "source_crop_validation_required", "runtime_enabled": False} for row in selected],
            "summary": {"question_count": len(selected), "answer_label_distribution": dict(Counter(row["correct_label"] for row in selected)),
                        "grade_distribution": dict(sorted(Counter(row["source_evidence"]["grade"] for row in selected).items())),
                        "section_count": len({(row["source_evidence"]["grade"], row["source_evidence"]["section_id"]) for row in selected})},
            "excluded_ids": sorted(exclude_ids), "answer_key_accessed": False, "student_data_accessed": False, "runtime_enabled": False, "qlora_enabled": False,
            "notice": "Private candidate pack only. Every question still requires source/crop validation and release testing."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exclude-id", action="append", default=[])
    args = parser.parse_args()
    gates = [json.loads(path.read_text(encoding="utf-8")) for path in args.gate]
    result = build(gates, exclude_ids=set(args.exclude_id))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
