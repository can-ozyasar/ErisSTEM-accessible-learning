"""Operate the private quality notebook for the Chatterbox V3 fine-tune path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import kaggle_ops


DATASET = "muhammedcanozyasar/eristem-tts-finetune-control-v1"
KERNEL = "muhammedcanozyasar/eristem-tts-chatterbox-v3-finetune-quality-v1"
TITLE = "Eristem Tts Chatterbox V3 Finetune Quality V1"
RUNNER = Path("experiments/kaggle/tts_chatterbox_v3_finetune_runner.py")


def control_directory() -> Path:
    directory = kaggle_ops.private_root() / "tts-finetune-control-v1"
    directory.mkdir(parents=True, exist_ok=True)
    control = directory / "control.json"
    control.write_text(json.dumps({"schema_version": "tts-finetune-control-v1", "contains_audio": False, "contains_transcripts": False, "run_mode": "quality"}, indent=2), encoding="utf-8")
    return directory


def prepare() -> Path:
    package = kaggle_ops.kernel_package_directory(KERNEL)
    if package.exists():
        kaggle_ops.load_kernel_metadata(package, KERNEL, DATASET)
        return package
    return kaggle_ops.prepare_notebook_package(KERNEL, DATASET, kaggle_ops.repo_root() / RUNNER, TITLE, enable_internet=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="ErişSTEM private V3 fine-tune kalite laboratuvarı")
    parser.add_argument("command", choices=("check", "run", "status", "fetch", "download-artifact"))
    args = parser.parse_args()
    if args.command == "check":
        result = {"authenticated": kaggle_ops.verify(), "package": str(prepare()), "mode": "quality", "notice": "Archived quality-v1 run. Paired evaluation found a severe regression; new training is disabled until the shifted-token loss is corrected."}
    elif args.command == "run":
        raise RuntimeError("quality-v1 eğitimi aynı konum token kaybı nedeniyle yeniden başlatılamaz; düzeltilmiş eğitim tarifi gerekli")
    elif args.command == "status":
        result = {"notebook": KERNEL, "status": kaggle_ops.notebook_status(KERNEL)}
    else:
        destination, summaries = kaggle_ops.download_summaries(KERNEL)
        if args.command == "download-artifact":
            manifests = list(destination.rglob("artifact_manifest.json"))
            if len(manifests) != 1:
                raise RuntimeError("Tek artifact manifest bulunamadı")
            artifact = kaggle_ops.download_finetune_artifact(KERNEL, manifests[0])
            result = {"artifact_download": str(artifact)}
        else:
            result = {"output": str(destination), "summaries": summaries}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"TTS fine-tune laboratuvarı: {error}")
        raise SystemExit(1) from error
