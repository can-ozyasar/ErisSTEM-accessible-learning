"""Fail-closed validation and baseline counts for the contextual QLoRA candidate set."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ..tutor_dataset import CASES


def validate(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "ayt-history-contextual-coach-qlora-candidates-v1":
        raise ValueError("QLoRA aday manifesti gerekli")
    rows_by_split = {}
    for split in ("train", "dev", "sealed_test"):
        rows_by_split[split] = [json.loads(line) for line in (directory / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if line]
    all_rows = [row for rows in rows_by_split.values() for row in rows]
    group_counts = Counter(row.get("group_id") for row in all_rows)
    if len(group_counts) != 120 or any(count != 6 for count in group_counts.values()):
        raise ValueError("120 grubun her birinde altı örnek bulunmalı")
    for group_id in group_counts:
        cases = [row["case"] for row in all_rows if row["group_id"] == group_id]
        if sorted(cases) != sorted(CASES):
            raise ValueError(f"Koçluk durumları eksik: {group_id}")
    split_sections = {split: {row["section_key"] for row in rows} for split, rows in rows_by_split.items()}
    if any(split_sections[left] & split_sections[right] for left in split_sections for right in split_sections if left < right):
        raise ValueError("Kaynak bölümü ayrımlar arasında sızdı")
    forbidden = ("doğru şık", "doğru cevap", "cevap:")
    if any(any(token in row.get("completion", "").lower() for token in forbidden) for row in all_rows):
        raise ValueError("Cevap sızıntısı bulundu")
    return {"status": "candidate_ready_for_offline_experiment_gate", "question_groups": len(group_counts), "examples": len(all_rows),
            "splits": {name: {"groups": len({row['group_id'] for row in rows}), "examples": len(rows), "sections": len(split_sections[name])} for name, rows in rows_by_split.items()},
            "answer_leakage": 0, "section_overlap": 0, "runtime_enabled": False,
            "next_gate": "Kaggle_veya_Evren_egitiminden_once_sealed_test_protokolu_ve_kaynak_politikasi_onayi"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.input_dir)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
