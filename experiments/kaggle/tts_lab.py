"""One-command private Kaggle TTS experiment control; never a live app backend.

The existing sealed benchmark is mathematical calibration, not a history
lesson release.  Generated audio stays private until a separate review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import kaggle_ops

DATASET = "muhammedcanozyasar/eristem-meb9-tts-gold-v1"
KERNEL = "muhammedcanozyasar/eristem-tts-cb-v3-ref-v1"
GOLD = Path("data/private/eristem_meb9_tts_gold_v1/tts-gold-v1.json")


def preflight() -> dict[str, object]:
    gold = kaggle_ops.private_path(kaggle_ops.repo_root() / GOLD)
    ids = kaggle_ops.tts_gold_ids(gold)
    package = kaggle_ops.kernel_package_directory(KERNEL)
    metadata = kaggle_ops.load_kernel_metadata(package, KERNEL, DATASET)
    if metadata.get("enable_gpu") != "true" or metadata.get("enable_internet") != "true":
        raise ValueError("Private TTS notebook GPU/model indirme ayarları doğrulanamadı")
    return {"ready": True, "dataset": DATASET, "notebook": KERNEL,
            "sealed_items": len(ids), "package": str(package),
            "notice": "Kalibrasyon verisi; tarih dersi yayını veya fine-tune değildir."}


def authenticated_owner() -> dict[str, str]:
    identity = kaggle_ops.verify()
    if identity["authenticated_user"] != KERNEL.split("/", 1)[0]:
        raise ValueError("Kaggle hesabı private notebook sahibinden farklı; uzak iş başlatılmadı")
    return identity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ErişSTEM özel Kaggle TTS laboratuvarı")
    parser.add_argument("command", choices=("check", "run", "status", "fetch"))
    args = parser.parse_args(argv)
    if args.command == "check":
        result = preflight()
        result["authentication"] = authenticated_owner()
    elif args.command == "run":
        result = preflight()
        authenticated_owner()
        kaggle_ops.push_notebook(Path(str(result["package"])), KERNEL, DATASET, 3600, "NvidiaTeslaT4")
        result = {"started": True, "notebook": KERNEL,
                  "next": "python experiments/kaggle/tts_lab.py status"}
    elif args.command == "status":
        result = {"notebook": KERNEL, "status": kaggle_ops.notebook_status(KERNEL)}
    else:
        result = preflight()
        status = kaggle_ops.notebook_status(KERNEL)
        if "KernelWorkerStatus.COMPLETE" not in status:
            raise RuntimeError("Notebook henüz tamamlanmadı; önce status komutunu kullanın")
        destination, attempts = kaggle_ops.download_summaries(KERNEL)
        result = {"output": str(destination), "summaries": attempts,
                  "student_publication": "blocked_pending_review"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"TTS laboratuvarı: {error}", file=sys.stderr)
        raise SystemExit(1) from error
