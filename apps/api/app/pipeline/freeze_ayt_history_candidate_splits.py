"""Freeze 72/24/24 source-section grouped splits for unpublished AYT candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA = "ayt-history-candidate-split-v1"
TARGETS = {"development": 72, "retrieval_test": 24, "system_acceptance": 24}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _question_signature(question: str) -> str:
    value = unicodedata.normalize("NFKC", question).casefold()
    return re.sub(r"[^\w]+", " ", value).strip()


def _rank(seed: int, label: str) -> str:
    return hashlib.sha256(f"{seed}:{label}".encode()).hexdigest()


def _select(groups: list[tuple[str, list[dict]]], count: int, seed: int) -> set[str]:
    """Choose a deterministic exact-size subset without splitting a section."""
    ordered = sorted(groups, key=lambda item: (_rank(seed, item[0]), item[0]))
    # ``total -> selected group ids``.  Every state is generated once, in
    # deterministic order, so no implicit random/floating point choice enters
    # the frozen manifest.
    states: dict[int, tuple[str, ...]] = {0: ()}
    for key, rows in ordered:
        width = len(rows)
        for total, selected in sorted(states.items(), reverse=True):
            next_total = total + width
            if next_total <= count and next_total not in states:
                states[next_total] = (*selected, key)
    if count not in states:
        raise ValueError("Kaynak bölümünü bölmeden istenen split boyutu oluşturulamadı")
    return set(states[count])


def build(candidate_pack: dict, *, seed: int = 20261121) -> dict:
    if candidate_pack.get("schema") != "ayt-history-original-question-candidate-pack-v1":
        raise ValueError("Özgün AYT Tarih aday paketi gerekli")
    questions = candidate_pack.get("questions", [])
    if len(questions) != sum(TARGETS.values()) or len({row.get("id") for row in questions}) != len(questions):
        raise ValueError("Benzersiz tam 120 aday soru gerekli")
    if any(row.get("runtime_enabled") is not False or row.get("status") != "source_crop_validation_required" for row in questions):
        raise ValueError("Yalnız yayıma kapalı kaynak-kırpım adayları bölünebilir")
    signatures: dict[str, tuple[str, str]] = {}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in questions:
        evidence = row.get("source_evidence", {})
        source_id, section_id = evidence.get("source_id"), evidence.get("section_id")
        if not isinstance(source_id, str) or not isinstance(section_id, str) or not evidence.get("source_checksum"):
            raise ValueError("Her aday kaynak, checksum ve bölüm kimliği taşımalı")
        signature = _question_signature(str(row.get("question", "")))
        if not signature:
            raise ValueError("Soru metni boş olamaz")
        group_key = (source_id, section_id)
        previous = signatures.setdefault(signature, group_key)
        if previous != group_key:
            raise ValueError("Aynı soru metni farklı kaynak bölümlerinde split sızıntısı oluşturuyor")
        groups[group_key].append(row)

    by_source: dict[str, list[tuple[str, list[dict]]]] = defaultdict(list)
    for (source_id, section_id), rows in groups.items():
        by_source[source_id].append((f"{source_id}:{section_id}", rows))
    source_sizes = {source_id: sum(len(rows) for _, rows in values) for source_id, values in by_source.items()}
    # Largest-remainder allocation of each 24-question holdout, independently
    # but deterministically. With this pack it yields 5/5/3/11 by source.
    exact = {source_id: size * TARGETS["retrieval_test"] / len(questions) for source_id, size in source_sizes.items()}
    allocation = {source_id: int(value) for source_id, value in exact.items()}
    remaining = TARGETS["retrieval_test"] - sum(allocation.values())
    for source_id in sorted(source_sizes, key=lambda key: (-(exact[key] - allocation[key]), key))[:remaining]:
        allocation[source_id] += 1
    retrieval, acceptance = set(), set()
    for source_id in sorted(by_source):
        source_groups = by_source[source_id]
        target = allocation[source_id]
        first = _select(source_groups, target, seed)
        remaining_groups = [group for group in source_groups if group[0] not in first]
        second = _select(remaining_groups, target, seed + 1)
        retrieval.update(first)
        acceptance.update(second)
    if retrieval & acceptance:
        raise ValueError("Kilitli retrieval ve kabul splitleri ayrık olmalı")

    rows = []
    for (source_id, section_id), members in sorted(groups.items()):
        key = f"{source_id}:{section_id}"
        split = "retrieval_test" if key in retrieval else "system_acceptance" if key in acceptance else "development"
        for question in sorted(members, key=lambda item: item["id"]):
            evidence = question["source_evidence"]
            rows.append({"id": question["id"], "split": split, "source_id": source_id,
                         "source_checksum": evidence["source_checksum"], "section_id": section_id,
                         "page": evidence["page"], "question_signature_sha256": hashlib.sha256(
                             _question_signature(question["question"]).encode()).hexdigest()})
    counts = Counter(row["split"] for row in rows)
    if dict(counts) != TARGETS:
        raise ValueError("72/24/24 split kotası sağlanamadı")
    split_groups = defaultdict(set)
    for row in rows:
        split_groups[(row["source_id"], row["section_id"])].add(row["split"])
    if any(len(value) != 1 for value in split_groups.values()):
        raise ValueError("Kaynak bölümü splitler arasında bölünemez")
    return {
        "schema": SCHEMA,
        "candidate_checksum": candidate_pack["candidate_checksum"],
        "corpus_checksum": candidate_pack["corpus_checksum"],
        "seed": seed,
        "targets": TARGETS,
        "records": sorted(rows, key=lambda row: row["id"]),
        "summary": {"counts": dict(counts), "source_counts": {
            split: dict(sorted(Counter(row["source_id"] for row in rows if row["split"] == split).items()))
            for split in TARGETS
        }, "source_section_group_count": len(groups), "exact_question_text_cross_section_duplicates": 0},
        "answer_key_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "is_human_teacher_approval": False,
        "notice": "Deterministic source-section grouped experimental split only. It detects exact question-text duplicates, not semantic/template paraphrases; no split enables publication, retrieval runtime, or QLoRA.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261121)
    args = parser.parse_args()
    pack = json.loads(args.candidate_pack.read_text(encoding="utf-8"))
    result = build(pack, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"]["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
