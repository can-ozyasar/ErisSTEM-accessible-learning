"""Private Kaggle QLoRA run for source-bound history coaching.

Input includes teacher-approved short question and MEB evidence excerpts. It
rejects PDFs, answer keys, coordinates, student data and sealed-test files.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

# Kaggle's T4 setting can expose two GPUs to one notebook process. TRL's
# SFTTrainer rejects that implicit DataParallel configuration, so QLoRA runs
# deliberately on a single visible GPU.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

MODEL = "Qwen/Qwen3-14B"
REVISION = "40c069824f4251a91eefaf281ebe4c544efd3e18"
INPUT = Path(os.getenv("TUTOR_QLORA_INPUT", "/kaggle/input/history-tutor-qlora-input-v1"))
OUT = Path("/kaggle/working/history-tutor-qwen3-14b-qlora-v1")
REPORT = OUT / "report.json"


def rows(name: str) -> list[dict]:
    path = INPUT / f"{name}.jsonl"
    if not path.is_file():
        raise ValueError(f"missing {path}")
    parsed = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not parsed:
        raise ValueError(f"{name} is empty")
    # Keep the completion boundary on a tokenizer-stable newline. Without it,
    # a trailing ``Koç:`` can merge with the first completion token and make
    # completion-only masking learn from a different prompt prefix.
    for item in parsed:
        item["prompt"] = item["prompt"].rstrip() + "\n"
    forbidden = ("answer_label", "answer_key", "source_text", "pdf", "bbox", "page", "answer_source_checked")
    groups: dict[str, set[str]] = {}
    for item in parsed:
        if set(item) != {"group_id", "case", "error_type", "prompt", "completion"}:
            raise ValueError("unexpected data field; export only reviewed coach examples")
        if any(word in json.dumps(item, ensure_ascii=False).lower() for word in forbidden):
            raise ValueError("source or answer material found in QLoRA input")
        group_cases = groups.setdefault(item["group_id"], set())
        if item["case"] in group_cases:
            raise ValueError("a coaching stage repeats within a question group")
        group_cases.add(item["case"])
    # Production defaults remain 84/18.  A private research pilot may set
    # explicit counts after its own readiness gate; this prevents a 17-group
    # pilot from being mistaken for the 120-group production set.
    expected_groups = int(os.getenv(
        "TUTOR_QLORA_EXPECTED_TRAIN_GROUPS" if name == "train" else "TUTOR_QLORA_EXPECTED_DEV_GROUPS",
        "84" if name == "train" else "18",
    ))
    if len(groups) != expected_groups or len(parsed) != expected_groups * 6:
        raise ValueError(f"{name} must contain {expected_groups} complete question groups and six cases each")
    if any(len(cases) != 6 for cases in groups.values()):
        raise ValueError("each question group must contain exactly six distinct coaching cases")
    return parsed


def group_ids(items: list[dict]) -> set[str]:
    return {item["group_id"] for item in items}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"model": MODEL, "revision": REVISION, "status": "started", "input": str(INPUT),
              "short_reviewed_evidence_included": True, "answer_keys_included": False}
    def save():
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        train, dev = rows("train"), rows("dev")
        overlap = group_ids(train) & group_ids(dev)
        if overlap:
            raise ValueError("train ve dev aynı soru grubunu içeremez")
        if (INPUT / "sealed_test.jsonl").exists():
            raise ValueError("sealed test must remain local and outside the Kaggle input")
        report["examples"] = {"train": len(train), "dev": len(dev)}
        if os.getenv("TUTOR_QLORA_SKIP_INSTALL") != "1":
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers>=4.51,<5",
                            "accelerate>=1.4", "peft>=0.14", "bitsandbytes>=0.45",
                            "trl>=0.15", "datasets>=3.2"], check=True)
        import torch
        from datasets import Dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from trl import SFTConfig, SFTTrainer

        if not torch.cuda.is_available():
            raise RuntimeError("Kaggle GPU is required")
        tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                                   bnb_4bit_compute_dtype=torch.float16)
        model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, quantization_config=quant,
                                                      device_map={"": 0}, torch_dtype=torch.float16)
        model.config.use_cache = False
        peft = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                          target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], task_type="CAUSAL_LM")
        learning_rate = float(os.getenv("TUTOR_QLORA_LR", "1e-4"))
        seed = int(os.getenv("TUTOR_QLORA_SEED", "42"))
        torch.manual_seed(seed)
        arguments = SFTConfig(output_dir=str(OUT / "checkpoints"), num_train_epochs=3,
                              per_device_train_batch_size=1, per_device_eval_batch_size=1,
                              gradient_accumulation_steps=8, gradient_checkpointing=True,
                              learning_rate=learning_rate, logging_steps=5, eval_strategy="epoch",
                              save_strategy="epoch", fp16=True, max_length=768,
                              completion_only_loss=True, report_to="none", seed=seed,
                              data_seed=seed)
        trainer = SFTTrainer(model=model, args=arguments, train_dataset=Dataset.from_list(train),
                             eval_dataset=Dataset.from_list(dev), processing_class=tokenizer, peft_config=peft)
        started = time.monotonic()
        trainer.train()
        metrics = trainer.evaluate()
        adapter = OUT / "adapter"
        trainer.model.save_pretrained(adapter)
        tokenizer.save_pretrained(OUT / "tokenizer")
        report.update({"status": "completed", "elapsed_seconds": round(time.monotonic() - started, 2),
                       "eval": {key: float(value) for key, value in metrics.items() if isinstance(value, (int, float))},
                       "adapter": str(adapter), "training": {"quantization": "nf4-4bit-fp16", "completion_only_loss": True,
                       "gradient_checkpointing": True, "epochs": 3, "learning_rate": learning_rate,
                       "lora": {"r": 16, "alpha": 32}, "seed": seed,
                       "packages": {name: version(name) for name in ("transformers", "accelerate", "peft", "bitsandbytes", "trl", "datasets")},
                       "selection_note": "Choose by reviewed development behaviour, not eval_loss alone."}})
    except Exception as error:
        report.update({"status": "failed", "error_type": type(error).__name__, "error": str(error)[:2000]})
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
