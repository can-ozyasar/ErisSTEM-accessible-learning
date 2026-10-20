"""Private Kaggle QLoRA experiment for a Turkish Socratic history tutor.

Input is a teacher-written JSONL under a private Kaggle Dataset. The script
does not manufacture training labels from answer keys or raw MEB paragraphs.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
DATA = Path(os.getenv("TUTOR_DATA", "/kaggle/input/eristem-history-tutor-private/dialogues.jsonl"))
OUTPUT = Path(os.getenv("TUTOR_OUTPUT", "/kaggle/working/history-tutor-adapter"))


def records(path: Path) -> tuple[list[dict], list[dict]]:
    if not path.is_file():
        raise FileNotFoundError(f"Private tutor dataset missing: {path}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    required = {"question_id", "split", "prompt", "completion", "stage", "source_ids"}
    if any(not required <= row.keys() for row in rows):
        raise ValueError("Every row needs question_id, split, prompt, completion, stage, source_ids")
    if any(row["split"] not in {"train", "eval"} for row in rows):
        raise ValueError("split must be train or eval")
    if any(not isinstance(row["source_ids"], list) or not row["source_ids"] for row in rows):
        raise ValueError("Every turn needs reviewed source IDs")
    if any(len(row["completion"]) > 350 or len(row["completion"]) < 20 for row in rows):
        raise ValueError("Teacher response must be a short, substantive TTS turn")
    if any(re.search(r"\b(?:doğru cevap|cevap [A-E]|şık [A-E] doğrudur)\b", row["completion"], re.IGNORECASE)
           for row in rows):
        raise ValueError("Answer-revealing training turn detected")
    train = [row for row in rows if row["split"] == "train"]
    evaluation = [row for row in rows if row["split"] == "eval"]
    if len(train) < 200 or len(evaluation) < 40:
        raise ValueError("At least 200 reviewed train and 40 held-out eval turns required")
    if {row["question_id"] for row in train} & {row["question_id"] for row in evaluation}:
        raise ValueError("Question IDs must not cross train/eval")
    return train, evaluation


def main():
    train, evaluation = records(DATA)
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                      bnb_4bit_compute_dtype=torch.float16,
                                      bnb_4bit_use_double_quant=True)
    config = SFTConfig(
        output_dir=str(OUTPUT), max_length=1536, per_device_train_batch_size=1,
        gradient_accumulation_steps=8, num_train_epochs=2, learning_rate=1e-4,
        eval_strategy="epoch", save_strategy="epoch", logging_steps=10,
        fp16=True, bf16=False, completion_only_loss=True, report_to="none",
        model_init_kwargs={"quantization_config": quantization, "device_map": "auto",
                           "dtype": torch.float16},
    )
    adapter = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                         target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    def dataset(rows):
        return Dataset.from_list([{"prompt": [{"role": "user", "content": row["prompt"]}],
                                   "completion": [{"role": "assistant", "content": row["completion"]}]}
                                  for row in rows])
    trainer = SFTTrainer(model=MODEL_ID, args=config, peft_config=adapter,
                         train_dataset=dataset(train), eval_dataset=dataset(evaluation))
    trainer.train()
    metrics = trainer.evaluate()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(OUTPUT / "adapter"))
    (OUTPUT / "metrics.json").write_text(json.dumps({"model": MODEL_ID,
        "train_turns": len(train), "eval_turns": len(evaluation),
        "stage_counts": dict(Counter(row["stage"] for row in train)),
        "eval_loss": metrics.get("eval_loss")}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "trained_requires_human_gate", "train": len(train),
                      "eval": len(evaluation), "eval_loss": metrics.get("eval_loss")}))


if __name__ == "__main__":
    main()
