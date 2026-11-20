"""Assemble reviewed contextual coaching into a private, section-disjoint QLoRA candidate set.

This is a dataset-preparation gate, not a training or runtime-release step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from ..tutor_dataset import CASES

SCHEMA = "ayt-history-contextual-coach-qlora-candidates-v1"
SPLITS = ("train", "dev", "sealed_test")
TARGETS = {"train": 72, "dev": 24, "sealed_test": 24}


def _stable_order(value: str) -> str:
    return hashlib.sha256(("eristem-section-split-v1:" + value).encode()).hexdigest()


def _assign_section_splits(questions: list[dict]) -> dict[str, str]:
    by_section: dict[str, list[str]] = defaultdict(list)
    for question in questions:
        evidence = question["source_evidence"]
        by_section[f"grade:{evidence['grade']}:section:{evidence['section_id']}"] .append(question["id"])
    totals = Counter()
    assigned: dict[str, str] = {}
    for section in sorted(by_section, key=_stable_order):
        size = len(by_section[section])
        # Assign whole source sections to the split most below its target.
        split = max(SPLITS, key=lambda name: ((TARGETS[name] - totals[name]) / TARGETS[name], -totals[name], name))
        assigned[section] = split
        totals[split] += size
    if not all(totals[name] for name in SPLITS):
        raise ValueError("Bölüm-temelli kapalı ayrım üretilemedi")
    return assigned


def build(pack: dict, inventory: dict, drafts: list[dict]) -> tuple[dict, dict[str, list[dict]]]:
    if pack.get("schema") != "ayt-history-question-bank-training-candidate-v1":
        raise ValueError("Donmuş soru-bankası paketi gerekli")
    if inventory.get("schema") != "ayt-history-contextual-coach-inventory-v1":
        raise ValueError("Bağlamsal koç envanteri gerekli")
    if inventory.get("question_bank_checksum") != pack.get("frozen_checksum"):
        raise ValueError("Envanter soru-bankası sürümüyle uyuşmuyor")
    questions = pack.get("questions", [])
    ids = {row["id"] for row in questions}
    if len(questions) != 120 or set(inventory.get("accepted", [])) != ids or inventory.get("rejected") or inventory.get("missing"):
        raise ValueError("Tam 120 kabul edilmiş, red ve eksik içermeyen koç envanteri gerekli")
    final: dict[str, dict] = {}
    for payload in drafts:
        if payload.get("schema") != "deepseek-contextual-source-bound-coaching-drafts-v1":
            continue
        if payload.get("question_bank_checksum") != pack["frozen_checksum"]:
            raise ValueError("Koç taslağı soru-bankası sürümüyle uyuşmuyor")
        for record in payload.get("records", []):
            if record.get("question_id") in ids:
                final[record["question_id"]] = record
    if set(final) != ids:
        raise ValueError("Kabul edilmiş her soru için son koç taslağı gerekli")
    question_by_id = {row["id"]: row for row in questions}
    section_splits = _assign_section_splits(questions)
    rows = {name: [] for name in SPLITS}
    for question_id in sorted(ids):
        question = question_by_id[question_id]
        record = final[question_id]
        turns = record.get("turns", [])
        if [turn.get("case") for turn in turns] != list(CASES):
            raise ValueError(f"Altı durum sözleşmesi bozuk: {question_id}")
        section = f"grade:{question['source_evidence']['grade']}:section:{question['source_evidence']['section_id']}"
        split = section_splits[section]
        for turn in turns:
            response = turn.get("guide_response", "")
            if turn.get("early_answer_disclosed") or any(word in response.lower() for word in ("doğru şık", "doğru cevap", "cevap:")):
                raise ValueError(f"Cevap sızıntısı: {question_id}:{turn.get('case')}")
            if len(turn.get("source_ids", [])) != 1 or len(turn.get("evidence_quotes", [])) != 1:
                raise ValueError(f"Kaynak bağı eksik: {question_id}:{turn.get('case')}")
            rows[split].append({
                "group_id": question_id, "case": turn["case"], "error_type": record["error_type"],
                "section_key": section, "source_id": turn["source_ids"][0],
                "evidence_quote": turn["evidence_quotes"][0], "learner_state": turn["learner_state"],
                "prompt": "Sen görme engelli AYT Tarih öğrencisine kısa, yargılamayan ve cevap sızdırmayan bir koçsun. "
                          f"Koçluk durumu: {turn['case']}\nSoru: {record['question']}\nÖğrenci: {turn['learner_state']}\n"
                          f"MEB kanıtı: {turn['evidence_quotes'][0]}\nKoç:",
                "completion": response,
                "runtime_enabled": False,
            })
    counts = Counter(row["group_id"] for bucket in rows.values() for row in bucket)
    if len(counts) != 120 or any(count != 6 for count in counts.values()):
        raise ValueError("Her soru grubu tek ayrımda altı örnek içermeli")
    split_sections = {name: sorted({row["section_key"] for row in bucket}) for name, bucket in rows.items()}
    if any(set(split_sections[left]) & set(split_sections[right]) for left in SPLITS for right in SPLITS if left < right):
        raise ValueError("Kaynak bölümü ayrımlar arasında sızdı")
    manifest = {"schema": SCHEMA, "corpus_checksum": pack["corpus_checksum"], "question_bank_checksum": pack["frozen_checksum"],
                "question_groups": 120, "examples": 720, "splits": {name: {"groups": len({row['group_id'] for row in bucket}), "examples": len(bucket), "sections": len(split_sections[name])} for name, bucket in rows.items()},
                "split_strategy": "source_section_disjoint_hash_greedy_v1", "contains_answer_keys": False,
                "runtime_enabled": False, "qlora_training_ready": False,
                "notice": "Private, independently reviewed candidate data only. Train/dev/sealed test are section-disjoint; training requires separate experiment approval and source-policy verification."}
    return manifest, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--draft", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    manifest, rows = build(load(args.pack), load(args.inventory), [load(path) for path in args.draft])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split, items in rows.items():
        (args.output_dir / f"{split}.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest["splits"], ensure_ascii=False))


if __name__ == "__main__":
    main()
