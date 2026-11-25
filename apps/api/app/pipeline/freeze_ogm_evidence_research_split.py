"""Freeze a leakage-resistant research split for source-grounded OGM questions.

The student-facing local-pilot pack deliberately keeps all eligible questions
as ``pilot``.  This separate, content-free manifest is for retrieval/QLoRA
evaluation only.  It assigns complete source-deneme groups together, so a
nearby question from the same source test cannot be used to train and score a
model at the same time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


SCHEMA = "ogm-ayt-source-grounded-research-split-v1"
_GROUP = re.compile(r":(d[1-9][0-9]*):p[1-9][0-9]*:q[1-9][0-9]*$")


def _stable_group_key(group_id: str) -> str:
    return hashlib.sha256(group_id.encode("utf-8")).hexdigest()


def _group_id(candidate_id: str) -> str:
    match = _GROUP.search(candidate_id)
    if not match:
        raise ValueError(f"deneme grubu okunamayan aday kimliği: {candidate_id}")
    return match.group(1)


def _best_assignment(groups: dict[str, list[str]], dev_target: int, sealed_target: int) -> dict[str, str]:
    """Use a tiny deterministic DP to keep whole groups while balancing counts."""
    ordered = sorted(groups, key=_stable_group_key)
    # (dev_count, sealed_count) -> assignment tuple in ordered group order.
    states: dict[tuple[int, int], tuple[str, ...]] = {(0, 0): ()}
    for group in ordered:
        size = len(groups[group])
        next_states: dict[tuple[int, int], tuple[str, ...]] = {}
        for (dev, sealed), assignment in states.items():
            for label, next_dev, next_sealed in (
                ("train", dev, sealed),
                ("development", dev + size, sealed),
                ("sealed_test", dev, sealed + size),
            ):
                key = (next_dev, next_sealed)
                candidate = assignment + (label,)
                # The first one is deterministic because ordered and labels are fixed.
                if key not in next_states:
                    next_states[key] = candidate
        states = next_states
    # Prefer exact targets, then the closest balanced result.  Both hold-out
    # partitions must remain non-empty; otherwise the manifest is useless.
    eligible = [(key, assignment) for key, assignment in states.items() if key[0] and key[1]]
    if not eligible:
        raise ValueError("geliştirme ve kilitli test için ayrı deneme grupları gerekli")
    (_, _), assignment = min(
        eligible,
        key=lambda item: (
            abs(item[0][0] - dev_target) + abs(item[0][1] - sealed_target),
            abs(item[0][0] - item[0][1]),
            item[0],
            item[1],
        ),
    )
    return dict(zip(ordered, assignment, strict=True))


def build(package: dict) -> dict:
    if package.get("schema") != "ogm-ayt-history-source-grounded-pilot-candidates-v1":
        raise ValueError("kaynak-bağlı OGM aday paketi gerekli")
    if package.get("runtime_enabled") is not False:
        raise ValueError("yalnız çalışma zamanına kapalı aday paketi bölünebilir")
    questions = package.get("questions", [])
    if len(questions) < 24:
        raise ValueError("anlamlı geliştirme ve kilitli test için en az 24 soru gerekli")
    ids = [row.get("candidate_id") for row in questions]
    if any(not isinstance(identifier, str) for identifier in ids) or len(set(ids)) != len(ids):
        raise ValueError("benzersiz aday kimlikleri gerekli")
    groups: dict[str, list[str]] = defaultdict(list)
    for identifier in ids:
        groups[_group_id(identifier)].append(identifier)
    if len(groups) < 3:
        raise ValueError("en az üç bağımsız deneme grubu gerekli")
    total = len(ids)
    group_splits = _best_assignment(groups, dev_target=round(total * 0.2), sealed_target=round(total * 0.2))
    splits = {identifier: group_splits[_group_id(identifier)] for identifier in ids}
    split_counts = {label: list(splits.values()).count(label) for label in ("train", "development", "sealed_test")}
    if not split_counts["development"] or not split_counts["sealed_test"]:
        raise ValueError("boş değerlendirme bölümü üretilemez")
    return {
        "schema": SCHEMA,
        "source_checksum": package["source_checksum"],
        "candidate_package_checksum": hashlib.sha256(
            json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "question_count": total,
        "grouping": "source_deneme_id",
        "group_count": len(groups),
        "group_splits": group_splits,
        "splits": splits,
        "split_counts": split_counts,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": (
            "Content-free research split. It is not an exam pack and does not authorize training, "
            "runtime use, publication, or access to answer keys."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = json.loads(args.package.read_text(encoding="utf-8"))
    report = build(package)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"split_counts": report["split_counts"], "group_count": report["group_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
