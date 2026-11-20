"""Build an immutable Kaggle input for the final exact-resume QLoRA stage."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def contract_checksum(contract: dict) -> str:
    return hashlib.sha256(json.dumps(contract, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def build(source_input: Path, verified_checkpoint: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError("resume input hedefi zaten var; üstüne yazma yasaktır")
    manifest_path = source_input / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("özgün QLoRA manifesti okunamadı") from exc
    if (manifest.get("schema") != "eristem-tutor-qlora-experiment-input-v1"
            or manifest.get("training_contract", {}).get("epochs") != 3
            or any(manifest.get(flag) is not False for flag in ("answer_keys_included", "sealed_test_uploaded", "student_data_included"))):
        raise ValueError("yalnız güvenli, sabit 3-epoch QLoRA girdisi devam ettirilebilir")
    for name in ("train.jsonl", "dev.jsonl"):
        source = source_input / name
        if not source.is_file() or manifest.get("files", {}).get(name) != sha256(source):
            raise ValueError(f"özgün QLoRA girdi checksum uyuşmuyor: {name}")
    resume_manifest_path = verified_checkpoint / "resume_checkpoint_manifest.json"
    try:
        resume = json.loads(resume_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("doğrulanmış resume manifesti okunamadı") from exc
    checkpoint_name, files = resume.get("checkpoint_name"), resume.get("files")
    if (resume.get("schema") != "eristem-tutor-qlora-resume-checkpoint-v1"
            or resume.get("input_manifest_sha256") != sha256(manifest_path)
            or resume.get("training_contract_sha256") != contract_checksum(manifest["training_contract"])
            or not isinstance(checkpoint_name, str) or not isinstance(files, list)):
        raise ValueError("resume checkpoint özgün deney sözleşmesine bağlı değil")
    checkpoint = verified_checkpoint / checkpoint_name
    names = {item.get("path") for item in files if isinstance(item, dict)}
    required = {"trainer_state.json", "optimizer.pt", "scheduler.pt", "adapter_config.json"}
    if not required <= names or not ({"adapter_model.safetensors", "adapter_model.bin"} & names):
        raise ValueError("resume checkpoint tam eğitim durumu içermiyor")
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes"}:
            raise ValueError("resume checkpoint dosya manifesti geçersiz")
        path = checkpoint / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ValueError(f"resume checkpoint checksum uyuşmuyor: {item.get('path')}")
    output.mkdir(parents=True)
    for name in ("manifest.json", "train.jsonl", "dev.jsonl"):
        shutil.copy2(source_input / name, output / name)
    shutil.copy2(resume_manifest_path, output / "resume_checkpoint_manifest.json")
    shutil.copytree(checkpoint, output / checkpoint_name)
    return {"schema": "eristem-tutor-qlora-resume-input-v1", "checkpoint": checkpoint_name,
            "input_manifest_sha256": sha256(output / "manifest.json"), "checkpoint_files": len(files),
            "answer_keys_included": False, "sealed_test_uploaded": False, "student_data_included": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-input", type=Path, required=True)
    parser.add_argument("--verified-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_input, args.verified_checkpoint, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
