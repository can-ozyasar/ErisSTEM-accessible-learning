"""Inspect and archive the corrected private V3 T3 quality experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import kaggle_ops


DATASET = "muhammedcanozyasar/eristem-tts-finetune-control-v1"
KERNEL = "muhammedcanozyasar/eristem-tts-chatterbox-v3-finetune-quality-v2"


def main() -> int:
    parser = argparse.ArgumentParser(description="Düzeltilmiş V3 T3 eğitiminin private çıktıları")
    parser.add_argument("command", choices=("status", "fetch", "download-artifact"))
    args = parser.parse_args()
    package = kaggle_ops.kernel_package_directory(KERNEL)
    kaggle_ops.load_kernel_metadata(package, KERNEL, DATASET)
    if args.command == "status":
        result = {"notebook": KERNEL, "status": kaggle_ops.notebook_status(KERNEL)}
    else:
        destination, summaries = kaggle_ops.download_summaries(KERNEL)
        if args.command == "download-artifact":
            manifests = list(destination.rglob("artifact_manifest.json"))
            if len(manifests) != 1:
                raise RuntimeError("Tamamlanmış koşuda tek artefact manifesti bekleniyor")
            artifact = kaggle_ops.download_finetune_artifact(KERNEL, manifests[0])
            result = {"artifact_download": str(artifact), "summaries": summaries}
        else:
            result = {"output": str(destination), "summaries": summaries}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
