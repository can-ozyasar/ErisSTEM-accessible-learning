"""Private Kaggle QLoRA run for source-bound history coaching.

Input includes teacher-approved short question and MEB evidence excerpts. It
rejects PDFs, answer keys, coordinates, student data and sealed-test files.
"""
from __future__ import annotations

import json
import os
import hashlib
import inspect
import platform
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

# Kaggle's T4 setting can expose two GPUs to one notebook process. TRL's
# SFTTrainer rejects that implicit DataParallel configuration, so QLoRA runs
# deliberately on a single visible GPU.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
# Must be configured before importing torch; it helps prevent allocator
# fragmentation during 4-bit model load and subsequent adapter training.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

MODEL = "Qwen/Qwen3-14B"
REVISION = "40c069824f4251a91eefaf281ebe4c544efd3e18"
PLANNED_EPOCHS = 3
KAGGLE_DATASET_HANDLE = "muhammedcanozyasar/history-tutor-qlora-input-resume-v4"
INPUT = Path(os.getenv("TUTOR_QLORA_INPUT", "/kaggle/input/history-tutor-qlora-input-resume-v4"))
OUT = Path("/kaggle/working/history-tutor-qwen3-14b-qlora-v1")
REPORT = OUT / "report.json"
RUN_METADATA = OUT / "run_metadata.json"
ARTIFACT_MANIFEST = OUT / "artifact_manifest.json"
ACCEPTANCE_REPORT = OUT / "acceptance_report.json"
CHECKPOINT_MANIFEST = OUT / "resume_checkpoint_manifest.json"
PACKAGE_REQUIREMENTS = (
    "transformers>=4.51,<5", "accelerate>=1.4,<2", "peft>=0.14,<1",
    "bitsandbytes>=0.45,<1", "trl>=0.15,<1", "datasets>=3.2,<5",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_files(adapter: Path, tokenizer: Path) -> list[dict]:
    files = []
    for root in (adapter, tokenizer):
        for path in sorted(root.rglob("*")):
            if path.is_file():
                files.append({"path": str(path.relative_to(OUT)), "sha256": sha256(path), "bytes": path.stat().st_size})
    if not files or not any(item["path"].endswith("adapter_config.json") for item in files):
        raise RuntimeError("adapter artifact is incomplete")
    return files


def json_checksum(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def checkpoint_files(checkpoint: Path) -> list[dict]:
    """Return the complete resumable state, never merely the LoRA adapter."""
    required = {"trainer_state.json", "optimizer.pt", "scheduler.pt", "adapter_config.json"}
    names = {path.name for path in checkpoint.iterdir() if path.is_file()}
    if not required <= names or not ("adapter_model.safetensors" in names or "adapter_model.bin" in names):
        raise RuntimeError("resumable checkpoint is incomplete")
    return [{"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in sorted(checkpoint.iterdir()) if path.is_file()]


def write_checkpoint_manifest(checkpoint: Path, input_directory: Path, contract: dict) -> None:
    CHECKPOINT_MANIFEST.write_text(json.dumps({
        "schema": "eristem-tutor-qlora-resume-checkpoint-v1",
        "base_model": MODEL, "base_model_revision": REVISION,
        "input_manifest_sha256": sha256(input_directory / "manifest.json"),
        "training_contract_sha256": json_checksum(contract),
        "checkpoint_name": checkpoint.name,
        "files": checkpoint_files(checkpoint),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def verified_resume_checkpoint(input_directory: Path, contract: dict) -> Path | None:
    """Allow continuation only from a hash-bound full Trainer checkpoint."""
    configured = os.getenv("TUTOR_QLORA_RESUME_CHECKPOINT")
    # A stage-two Kaggle input contains the unchanged train/dev/manifest plus
    # this one verified checkpoint.  Environment configuration is retained for
    # non-Kaggle runners, but Kaggle needs no manually-entered notebook secret.
    manifest_path = (Path(configured).resolve().parent / "resume_checkpoint_manifest.json"
                     if configured else input_directory / "resume_checkpoint_manifest.json")
    if not configured and not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("resume checkpoint manifesti okunamadı") from exc
    checkpoint_name = manifest.get("checkpoint_name") if isinstance(manifest, dict) else None
    if not configured and (not isinstance(checkpoint_name, str) or not checkpoint_name.startswith("checkpoint-")):
        raise ValueError("resume checkpoint manifestinde checkpoint adı geçersiz")
    checkpoint = (Path(configured).resolve() if configured else (input_directory / checkpoint_name).resolve())
    if not checkpoint.is_dir() or not manifest_path.is_file():
        raise ValueError("resume checkpoint ve bitişiğindeki manifest zorunludur")
    if (manifest.get("schema") != "eristem-tutor-qlora-resume-checkpoint-v1"
            or manifest.get("base_model") != MODEL or manifest.get("base_model_revision") != REVISION
            or manifest.get("input_manifest_sha256") != sha256(input_directory / "manifest.json")
            or manifest.get("training_contract_sha256") != json_checksum(contract)
            or manifest.get("checkpoint_name") != checkpoint.name):
        raise ValueError("resume checkpoint sözleşmesi bu eğitim girdisiyle eşleşmiyor")
    declared = manifest.get("files")
    if not isinstance(declared, list) or declared != checkpoint_files(checkpoint):
        raise ValueError("resume checkpoint checksum veya dosya kümesi uyuşmuyor")
    return checkpoint


def resolve_input_directory() -> Path:
    """Find the one immutable QLoRA input mounted by Kaggle.

    Kaggle's classic image mounts a Dataset under its slug; the current
    private image mounts it under ``datasets/<owner>/<slug>``.  Both exact,
    metadata-derived locations are accepted.  Do not scan arbitrary mounted
    sources: the selected directory must be the dataset declared above.
    ``input_manifest`` verifies its schema and checksums afterwards.
    """
    owner, slug = KAGGLE_DATASET_HANDLE.split("/", maxsplit=1)
    allowed = (INPUT, Path("/kaggle/input") / slug, Path("/kaggle/input/datasets") / owner / slug)
    complete = tuple(path for path in allowed
                     if all((path / name).is_file() for name in ("manifest.json", "train.jsonl", "dev.jsonl")))
    if len(complete) != 1:
        present = [str(path) for path in allowed if path.exists()]
        raise ValueError(f"immutable QLoRA input manifest is required; allowed mounted paths={present}")
    return complete[0]


def input_manifest(input_directory: Path) -> dict:
    path = input_directory / "manifest.json"
    if not path.is_file():
        raise ValueError("immutable QLoRA input manifest is required")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "eristem-tutor-qlora-experiment-input-v1":
        raise ValueError("unexpected QLoRA input schema")
    if (manifest.get("base_model") != MODEL or manifest.get("base_model_revision") != REVISION
            or manifest.get("answer_keys_included") is not False or manifest.get("sealed_test_uploaded") is not False
            or manifest.get("student_data_included") is not False):
        raise ValueError("input manifest safety or model contract mismatch")
    if manifest.get("training_contract", {}).get("epochs") != PLANNED_EPOCHS:
        raise ValueError(f"QLoRA input must bind the preregistered {PLANNED_EPOCHS}-epoch contract")
    for name in ("train.jsonl", "dev.jsonl"):
        actual = hashlib.sha256((input_directory / name).read_bytes()).hexdigest()
        if manifest.get("files", {}).get(name) != actual:
            raise ValueError(f"input checksum mismatch: {name}")
    return manifest


def rows(name: str, manifest: dict, input_directory: Path) -> list[dict]:
    path = input_directory / f"{name}.jsonl"
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
    expected_groups = manifest["splits"][name]["groups"]
    if len(groups) != expected_groups or len(parsed) != expected_groups * 6:
        raise ValueError(f"{name} must contain {expected_groups} complete question groups and six cases each")
    if any(len(cases) != 6 for cases in groups.values()):
        raise ValueError("each question group must contain exactly six distinct coaching cases")
    return parsed


def runtime_preflight(torch, sft_config_type) -> dict:
    """Reject an incompatible Kaggle image before model weights are loaded."""
    if not torch.cuda.is_available():
        raise RuntimeError("Kaggle GPU is required")
    gpu = torch.cuda.get_device_properties(0)
    # A 14B NF4 model, fp32 LoRA weights and a 768-token batch need practical
    # headroom beyond the nominal 4-bit weight size.  A smaller GPU would turn
    # this registered run into an avoidable OOM experiment.
    if gpu.total_memory < 15_000_000_000:
        raise RuntimeError("QLoRA contract requires at least 15 GB of GPU memory")
    required_sft_fields = {
        "output_dir", "num_train_epochs", "gradient_accumulation_steps",
        "max_length", "completion_only_loss", "eval_strategy", "save_strategy",
    }
    missing = sorted(required_sft_fields - set(inspect.signature(sft_config_type).parameters))
    if missing:
        raise RuntimeError("installed TRL SFTConfig is incompatible: missing " + ", ".join(missing))
    packages = {name: version(name) for name in ("transformers", "accelerate", "peft", "bitsandbytes", "trl", "datasets")}
    return {
        "gpu_name": torch.cuda.get_device_name(0),
        "gpu_memory_bytes": gpu.total_memory,
        "gpu_capability": list(torch.cuda.get_device_capability(0)),
        "packages": packages,
        "sft_config_fields_checked": sorted(required_sft_fields),
    }


def prepare_quantized_qwen_for_lora(model, torch) -> dict:
    """Prepare a 4-bit Qwen model without upcasting its huge frozen heads.

    PEFT's generic ``prepare_model_for_kbit_training`` converts *all*
    non-quantized fp16 parameters to fp32.  For Qwen3-14B that includes a
    multi-gigabyte vocabulary head and exceeds a 16 GB T4 before LoRA is even
    attached.  QLoRA only needs frozen base weights, stable small norm weights,
    input gradients and activation checkpointing; perform exactly those steps.
    """
    norm_parameters, frozen_parameters = 0, 0
    for name, parameter in model.named_parameters():
        parameter.requires_grad = False
        frozen_parameters += parameter.numel()
        if "norm" in name.lower() and parameter.dtype in (torch.float16, torch.bfloat16):
            parameter.data = parameter.data.to(torch.float32)
            norm_parameters += parameter.numel()
    if not hasattr(model, "enable_input_require_grads") or not hasattr(model, "gradient_checkpointing_enable"):
        raise RuntimeError("Qwen model does not expose required QLoRA gradient hooks")
    model.enable_input_require_grads()
    model.gradient_checkpointing_enable()
    return {
        "method": "explicit-frozen-base-small-norm-fp32",
        "frozen_parameter_count": frozen_parameters,
        "fp32_norm_parameter_count": norm_parameters,
        "large_embedding_or_lm_head_upcast": False,
    }


def group_ids(items: list[dict]) -> set[str]:
    return {item["group_id"] for item in items}


def requested_stop_epoch(contract: dict, *, has_resume_checkpoint: bool) -> int | None:
    """Optionally split one fixed run without changing its epoch contract."""
    raw = os.getenv("TUTOR_QLORA_STOP_AFTER_EPOCH")
    if not raw:
        # Kaggle's cancellation history makes the first two epochs a durable
        # stage. A detected verified checkpoint always means final continuation.
        return None if has_resume_checkpoint else 2
    try:
        stop_epoch = int(raw)
    except ValueError as exc:
        raise ValueError("TUTOR_QLORA_STOP_AFTER_EPOCH tam sayı olmalı") from exc
    if not 1 <= stop_epoch < contract["epochs"]:
        raise ValueError("stop epoch 1 ile planlanan son epoch arasında olmalı")
    if os.getenv("TUTOR_QLORA_RESUME_CHECKPOINT"):
        raise ValueError("resume koşumunda stop epoch kullanılamaz")
    return stop_epoch


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"model": MODEL, "revision": REVISION, "status": "started", "input": str(INPUT),
              "short_reviewed_evidence_included": True, "answer_keys_included": False,
              "runtime_enabled": False, "platform": platform.platform()}
    def save():
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        # This allowlisted summary intentionally contains no question, source
        # excerpt, answer key, completion, or student material.
        safe = {key: value for key, value in report.items() if key not in {"input", "adapter"}}
        RUN_METADATA.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        input_directory = resolve_input_directory()
        report["input"] = str(input_directory)
        manifest = input_manifest(input_directory)
        train, dev = rows("train", manifest, input_directory), rows("dev", manifest, input_directory)
        overlap = group_ids(train) & group_ids(dev)
        if overlap:
            raise ValueError("train ve dev aynı soru grubunu içeremez")
        if (input_directory / "sealed_test.jsonl").exists():
            raise ValueError("sealed test must remain local and outside the Kaggle input")
        report["examples"] = {"train": len(train), "dev": len(dev)}
        report["input_manifest"] = {"schema": manifest["schema"], "candidate_manifest_sha256": manifest["candidate_manifest_sha256"],
                                    "files": manifest["files"]}
        if os.getenv("TUTOR_QLORA_SKIP_INSTALL") != "1":
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "-q", *PACKAGE_REQUIREMENTS], check=True)
        import torch
        from datasets import Dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainerCallback
        from trl import SFTConfig, SFTTrainer

        report["preflight"] = runtime_preflight(torch, SFTConfig)
        report["gpu"] = {"count": torch.cuda.device_count(), "name": torch.cuda.get_device_name(0),
                         "total_memory_bytes": torch.cuda.get_device_properties(0).total_memory}
        tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                                   bnb_4bit_compute_dtype=torch.float16)
        model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, quantization_config=quant,
                                                      device_map={"": 0}, torch_dtype=torch.float16)
        model.config.use_cache = False
        contract = manifest["training_contract"]
        resume_checkpoint = verified_resume_checkpoint(input_directory, contract)
        stop_epoch = requested_stop_epoch(contract, has_resume_checkpoint=resume_checkpoint is not None)
        report["qlora_preparation"] = prepare_quantized_qwen_for_lora(model, torch)
        adapter = contract["adapter"]
        peft = LoraConfig(r=adapter["r"], lora_alpha=adapter["alpha"], lora_dropout=adapter["dropout"],
                          target_modules=adapter["target_modules"], task_type="CAUSAL_LM")
        learning_rate = contract["learning_rate"]
        seed = contract["seed"]
        torch.manual_seed(seed)
        arguments = SFTConfig(output_dir=str(OUT / "checkpoints"), num_train_epochs=contract["epochs"],
                              per_device_train_batch_size=contract["per_device_batch_size"], per_device_eval_batch_size=1,
                              gradient_accumulation_steps=contract["gradient_accumulation_steps"], gradient_checkpointing=True,
                              learning_rate=learning_rate, logging_steps=5, eval_strategy="epoch",
                              save_strategy="epoch", fp16=True, bf16=False, max_length=contract["max_length"],
                              completion_only_loss=True, report_to="none", seed=seed, optim=contract["optimizer"],
                              data_seed=seed)

        class StopAfterEpoch(TrainerCallback):
            """Request a durable epoch checkpoint before a time-limited session exits."""
            def on_epoch_end(self, _args, state, control, **_kwargs):
                if stop_epoch is not None and state.epoch is not None and state.epoch >= stop_epoch:
                    control.should_save = True
                    control.should_training_stop = True
                return control

        trainer = SFTTrainer(model=model, args=arguments, train_dataset=Dataset.from_list(train),
                             eval_dataset=Dataset.from_list(dev), processing_class=tokenizer, peft_config=peft,
                             callbacks=[StopAfterEpoch()] if stop_epoch is not None else None)
        # The 4-bit base model computes in fp16, but LoRA adapters must retain
        # fp32 master weights on a T4.  AMP's GradScaler may unscale fp32
        # gradients, whereas it rejects both bf16 and fp16 adapter gradients.
        # Frozen quantized base weights stay untouched.
        trainable_dtypes: dict[str, int] = {}
        for parameter in trainer.model.parameters():
            if parameter.requires_grad and parameter.dtype != torch.float32:
                parameter.data = parameter.data.to(dtype=torch.float32)
            if parameter.requires_grad:
                name = str(parameter.dtype).removeprefix("torch.")
                trainable_dtypes[name] = trainable_dtypes.get(name, 0) + parameter.numel()
        torch.cuda.reset_peak_memory_stats(0)
        started = time.monotonic()
        trainer.train(resume_from_checkpoint=str(resume_checkpoint) if resume_checkpoint else None)
        metrics = trainer.evaluate()
        checkpoints = sorted((OUT / "checkpoints").glob("checkpoint-*"),
                             key=lambda path: int(path.name.removeprefix("checkpoint-")))
        if not checkpoints:
            raise RuntimeError("epoch checkpoint oluşturulmadı; koşum yeniden başlatılamaz")
        latest_checkpoint = checkpoints[-1]
        write_checkpoint_manifest(latest_checkpoint, input_directory, contract)
        adapter = OUT / "adapter"
        trainer.model.save_pretrained(adapter)
        tokenizer_dir = OUT / "tokenizer"
        tokenizer.save_pretrained(tokenizer_dir)
        artifacts = artifact_files(adapter, tokenizer_dir)
        ARTIFACT_MANIFEST.write_text(json.dumps({
            "schema": "eristem-tutor-qlora-adapter-artifact-v1", "base_model": MODEL, "base_model_revision": REVISION,
            "input_manifest_sha256": sha256(input_directory / "manifest.json"), "files": artifacts,
            "resume_checkpoint_manifest_sha256": sha256(CHECKPOINT_MANIFEST),
            "runtime_enabled": False,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        # Training metrics are evidence of optimization, not product acceptance.
        # The adapter remains blocked until the local sealed safety/rubric review
        # has compared it with the base model.
        acceptance = {
            "schema": "eristem-tutor-qlora-acceptance-v1",
            "adapter_artifact_manifest_sha256": sha256(ARTIFACT_MANIFEST),
            "dev_metrics": {key: float(value) for key, value in metrics.items() if isinstance(value, (int, float))},
            "training_progress": {
                "planned_epochs": contract["epochs"], "completed_epoch": trainer.state.epoch,
                "global_step": trainer.state.global_step, "resumed_from_checkpoint": bool(resume_checkpoint),
                "checkpoint_manifest_sha256": sha256(CHECKPOINT_MANIFEST),
            },
            "metric_protocol": {
                "optimization": ["eval_loss", "eval_runtime", "eval_samples_per_second"],
                "paired_development": ["early_answer_disclosure_rate", "source_external_claim_rate",
                                       "wrong_source_attribution_rate", "socratic_question_rate",
                                       "abstain_when_evidence_missing_rate", "turkish_rate",
                                       "response_token_p50", "response_token_p95", "first_token_p50_ms",
                                       "first_token_p95_ms", "full_response_p50_ms", "full_response_p95_ms"],
                "acceptance_rule": "Dev karşılaştırması tamamlanmadan sealed test çalıştırılmaz; kritik üç ihlal oranı sıfır olmalıdır.",
            },
            "required_gates": {
                "base_model_paired_comparison": "pending",
                "sealed_test_once": "pending",
                "early_answer_disclosure": "pending_must_be_zero",
                "source_external_claim": "pending_must_be_zero",
                "wrong_source_attribution": "pending_must_be_zero",
                "expert_blind_rubric": "pending",
                "latency_p50_p95": "pending",
            },
            "decision": ("checkpoint_ready_pending_exact_resume" if stop_epoch is not None
                         else "blocked_pending_local_sealed_evaluation"),
        }
        ACCEPTANCE_REPORT.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2), encoding="utf-8")
        report.update({"status": "checkpoint_ready" if stop_epoch is not None else "completed",
                       "elapsed_seconds": round(time.monotonic() - started, 2),
                       "eval": {key: float(value) for key, value in metrics.items() if isinstance(value, (int, float))},
                       "adapter": str(adapter), "training": {"quantization": "nf4-4bit-fp16", "completion_only_loss": True,
                       "gradient_checkpointing": True, "epochs": contract["epochs"], "learning_rate": learning_rate,
                       "stop_after_epoch": stop_epoch, "resumed_from_checkpoint": bool(resume_checkpoint),
                       "latest_checkpoint": latest_checkpoint.name,
                       "lora": {"r": 16, "alpha": 32}, "seed": seed,
                       "trainable_parameter_dtypes": trainable_dtypes,
                       "packages": report["preflight"]["packages"],
                       "selection_note": "Choose by preregistered reviewed development behaviour, never eval_loss alone.",
                       "contract": contract,
                       "parameters": {"total": sum(p.numel() for p in trainer.model.parameters()),
                                      "trainable": sum(p.numel() for p in trainer.model.parameters() if p.requires_grad)},
                       "peak_gpu_memory_bytes": torch.cuda.max_memory_allocated(0),
                       "artifact_file_count": len(artifacts)}})
    except Exception as error:
        report.update({"status": "failed", "error_type": type(error).__name__, "error": str(error)[:2000]})
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
