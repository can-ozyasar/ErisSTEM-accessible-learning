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
from pathlib import Path

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
    forbidden = ("answer_label", "answer_key", "source_text", "pdf", "bbox", "page", "answer_source_checked")
    groups = set()
    for item in parsed:
        if set(item) != {"group_id", "case", "error_type", "prompt", "completion"}:
            raise ValueError("unexpected data field; export only reviewed coach examples")
        if any(word in json.dumps(item, ensure_ascii=False).lower() for word in forbidden):
            raise ValueError("source or answer material found in QLoRA input")
        if item["group_id"] in groups:
            # Three turns are permitted per group, but a stage cannot repeat.
            continue
        groups.add(item["group_id"])
    return parsed


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"model": MODEL, "revision": REVISION, "status": "started", "input": str(INPUT),
              "short_reviewed_evidence_included": True, "answer_keys_included": False}
    def save():
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        train, dev = rows("train"), rows("dev")
        if (INPUT / "sealed_test.jsonl").exists():
            raise ValueError("sealed test must remain local and outside the Kaggle input")
        report["examples"] = {"train": len(train), "dev": len(dev)}
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers==5.3.0", "accelerate==1.12.0",
                        "peft==0.18.1", "bitsandbytes==0.49.2", "trl==0.29.0", "datasets==4.0.0"], check=True)
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
                                                      device_map={"": 0}, dtype=torch.float16)
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
                       "selection_note": "Choose by reviewed development behaviour, not eval_loss alone."}})
    except Exception as error:
        report.update({"status": "failed", "error_type": type(error).__name__, "error": str(error)[:2000]})
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
