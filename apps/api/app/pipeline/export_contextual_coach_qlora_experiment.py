"""Create a minimal, immutable Kaggle input from the validated local candidate set.

The sealed split never leaves the local directory.  This module deliberately
does not start training or publish a dataset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..tutor_dataset import CASES


SCHEMA = "eristem-tutor-qlora-experiment-input-v1"
MODEL = "Qwen/Qwen3-14B"
REVISION = "40c069824f4251a91eefaf281ebe4c544efd3e18"
TRAINING = {
    "quantization": {"load_in_4bit": True, "type": "nf4", "double_quant": True, "compute_dtype": "float16"},
    "adapter": {"target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"], "r": 16, "alpha": 32, "dropout": 0.05},
    "optimizer": "paged_adamw_8bit", "learning_rate": 0.0001, "epochs": 3,
    "per_device_batch_size": 1, "gradient_accumulation_steps": 8, "max_length": 768,
    "completion_only_loss": True, "seed": 42,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError(f"Boş aday ayrımı: {path.name}")
    required = {"group_id", "case", "error_type", "section_key", "source_id", "evidence_quote", "learner_state", "prompt", "completion", "runtime_enabled"}
    if any(set(row) != required or row["runtime_enabled"] is not False for row in rows):
        raise ValueError("Kaynak aday satırı sözleşmesi bozuk")
    grouped: dict[str, set[str]] = {}
    for row in rows:
        grouped.setdefault(row["group_id"], set()).add(row["case"])
    if any(cases != set(CASES) for cases in grouped.values()) or len(rows) != len(grouped) * len(CASES):
        raise ValueError("Her QLoRA soru grubunda altı benzersiz koçluk durumu gerekli")
    return rows


def build(input_dir: Path, output_dir: Path, *, epochs: int = 3) -> dict:
    if not 1 <= epochs <= 3:
        raise ValueError("epochs 1 ile 3 arasında olmalı")
    candidate = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    if candidate.get("schema") != "ayt-history-contextual-coach-qlora-candidates-v1" or candidate.get("contains_answer_keys") is not False:
        raise ValueError("Doğrulanmış, cevap anahtarı içermeyen koç aday paketi gerekli")
    train, dev = (_read_rows(input_dir / f"{name}.jsonl") for name in ("train", "dev"))
    if {row["group_id"] for row in train} & {row["group_id"] for row in dev}:
        raise ValueError("Eğitim ve geliştirme soru grupları çakışıyor")
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = ("group_id", "case", "error_type", "prompt", "completion")
    for name, rows in (("train", train), ("dev", dev)):
        (output_dir / f"{name}.jsonl").write_text(
            "".join(json.dumps({field: row[field] for field in fields}, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema": SCHEMA, "base_model": MODEL, "base_model_revision": REVISION,
        "candidate_manifest_sha256": _sha256(input_dir / "manifest.json"),
        "candidate_question_bank_checksum": candidate["question_bank_checksum"],
        "splits": {"train": {"groups": len({r['group_id'] for r in train}), "examples": len(train)},
                   "dev": {"groups": len({r['group_id'] for r in dev}), "examples": len(dev)}},
        "training_contract": {**TRAINING, "epochs": epochs},
        "inference_contract": {"enable_thinking": False, "max_new_tokens": 96, "temperature": 0.2,
                               "reason": "Sesli koçta kısa, öngörülebilir tek-soru yanıt ve düşük gecikme gerekir."},
        "answer_keys_included": False, "sealed_test_uploaded": False, "student_data_included": False,
        "runtime_enabled": False,
        "acceptance_gate": {"dev_is_for_selection_only": True, "sealed_test_runs_once_after_selection": True,
                            "required_zero_metrics": ["early_answer_disclosure", "source_external_claim", "checksum_mismatch"]},
    }
    manifest["files"] = {name: _sha256(output_dir / name) for name in ("train.jsonl", "dev.jsonl")}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(build(args.input_dir, args.output_dir, epochs=args.epochs), ensure_ascii=False))


if __name__ == "__main__":
    main()
