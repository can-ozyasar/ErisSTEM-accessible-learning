"""One-command private Kaggle TTS experiments; never a live app backend."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import kaggle_ops

PROFILES = {
    "history": {
        "dataset": "muhammedcanozyasar/eristem-history-tts-eval-v1",
        "kernel": "muhammedcanozyasar/eristem-history-tts-chatterbox-v3-v2",
        "manifest": Path("data/private/eristem_history_tts_eval_v1/tts-history-eval-v1.json"),
        "runner": Path("experiments/kaggle/tts_chatterbox_v3_reference_runner.py"),
        "title": "Eristem History Tts Chatterbox V3 V2",
    },
    "stem": {
        "dataset": "muhammedcanozyasar/eristem-meb9-tts-gold-v1",
        "kernel": "muhammedcanozyasar/eristem-tts-cb-v3-ref-v1",
        "manifest": Path("data/private/eristem_meb9_tts_gold_v1/tts-gold-v1.json"),
    },
}


def preflight(profile: str) -> dict[str, object]:
    config = PROFILES[profile]
    manifest = kaggle_ops.private_path(kaggle_ops.repo_root() / config["manifest"])
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if profile == "history":
        if payload.get("schema_version") != "tts-history-eval-v1" or payload.get("evaluation_only") is not True:
            raise ValueError("Tarih ses değerlendirme manifesti geçersiz")
        source = kaggle_ops.repo_root() / "data/meb/tarih-9sinif-ders-kitabi_20261006.pdf"
        if kaggle_ops.sha256(source) != payload.get("source", {}).get("pdf_sha256"):
            raise ValueError("Tarih PDF checksum uyuşmuyor; Kaggle'a veri gönderilmedi")
        items = payload.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 40:
            raise ValueError("Tarih ses değerlendirme örnek sayısı geçersiz")
        ids = [item.get("id") for item in items if isinstance(item, dict)]
        if len(ids) != len(items) or any(not isinstance(item_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", item_id) for item_id in ids) or len(set(ids)) != len(ids) or any(
            not isinstance(item.get("expected_spoken_text"), str)
            or not 1 <= len(item["expected_spoken_text"]) <= 500
            or item.get("page") not in {40, 41, 42}
            or item.get("kind") not in {"text", "exercise"}
            for item in items if isinstance(item, dict)
        ):
            raise ValueError("Tarih ses değerlendirme girdileri geçersiz")
    else:
        ids = kaggle_ops.tts_gold_ids(manifest)
    kernel, dataset = str(config["kernel"]), str(config["dataset"])
    package = kaggle_ops.kernel_package_directory(kernel)
    if package.exists():
        metadata = kaggle_ops.load_kernel_metadata(package, kernel, dataset)
        if metadata.get("enable_gpu") != "true" or metadata.get("enable_internet") != "true":
            raise ValueError("Private TTS notebook GPU/model indirme ayarları doğrulanamadı")
    elif profile != "history":
        raise ValueError("TTS notebook paketi bulunamadı")
    return {"ready": True, "profile": profile, "dataset": dataset, "notebook": kernel,
            "sealed_items": len(ids), "input_sha256": kaggle_ops.sha256(manifest),
            "package": str(package), "package_prepared": package.exists(),
            "notice": "Yalnız ses değerlendirmesi; öğrenci yayını veya fine-tune değildir."}


def authenticated_owner(kernel: str) -> dict[str, str]:
    identity = kaggle_ops.verify()
    if identity["authenticated_user"] != kernel.split("/", 1)[0]:
        raise ValueError("Kaggle hesabı private notebook sahibinden farklı; uzak iş başlatılmadı")
    return identity


def prepare_history_package() -> Path:
    config = PROFILES["history"]
    package = kaggle_ops.kernel_package_directory(str(config["kernel"]))
    if package.exists():
        kaggle_ops.load_kernel_metadata(package, str(config["kernel"]), str(config["dataset"]))
        return package
    return kaggle_ops.prepare_notebook_package(
        str(config["kernel"]), str(config["dataset"]),
        kaggle_ops.repo_root() / config["runner"], str(config["title"]),
        enable_internet=True,
        source_replacements=(
            ("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-tts-gold-v1",
             "/kaggle/input/datasets/muhammedcanozyasar/eristem-history-tts-eval-v1"),
            ("/kaggle/working/eristem-private-tts-chatterbox-v3-reference-v1",
             "/kaggle/working/eristem-history-tts-chatterbox-v3-v2"),
            ('"tts-gold-v1.json"', '"tts-history-eval-v1.json"'),
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ErişSTEM özel Kaggle TTS laboratuvarı")
    parser.add_argument("command", choices=("check", "run", "status", "fetch"))
    parser.add_argument("--profile", choices=tuple(PROFILES), default="history")
    args = parser.parse_args(argv)
    config = PROFILES[args.profile]
    kernel, dataset = str(config["kernel"]), str(config["dataset"])
    if args.command == "check":
        result = preflight(args.profile)
        result["authentication"] = authenticated_owner(kernel)
    elif args.command == "run":
        result = preflight(args.profile)
        authenticated_owner(kernel)
        if args.profile == "history":
            package = prepare_history_package()
            kaggle_ops.upload_dataset(
                kaggle_ops.repo_root() / config["manifest"].parent, dataset,
                "Private source-bound history TTS acoustic evaluation v1",
            )
        else:
            package = Path(str(result["package"]))
        kaggle_ops.push_notebook(package, kernel, dataset, 3600, "NvidiaTeslaT4")
        result = {"started": True, "notebook": kernel,
                  "next": "python experiments/kaggle/tts_lab.py status --profile " + args.profile}
    elif args.command == "status":
        result = {"notebook": kernel, "status": kaggle_ops.notebook_status(kernel)}
    else:
        result = preflight(args.profile)
        status = kaggle_ops.notebook_status(kernel)
        if "KernelWorkerStatus.COMPLETE" not in status:
            raise RuntimeError("Notebook henüz tamamlanmadı; önce status komutunu kullanın")
        destination, attempts = kaggle_ops.download_summaries(kernel)
        records = list(destination.rglob("run_records.json"))
        if len(records) != 1:
            raise RuntimeError("Tek bir tamamlanmış TTS raporu bulunamadı")
        report = json.loads(records[0].read_text(encoding="utf-8"))
        if args.profile == "history" and report.get("input_sha256") != result["input_sha256"]:
            raise RuntimeError("Kaggle sesleri mevcut tarih değerlendirme girdisine ait değil")
        audio = None
        if args.profile == "history" and report.get("items_failed") == 0:
            audio = kaggle_ops.download_tts_audio(kernel, records[0])
        result = {"output": str(destination), "summaries": attempts,
                  "audio": str(audio) if audio else None,
                  "items_generated": report.get("items_generated"),
                  "items_failed": report.get("items_failed"),
                  "student_publication": "blocked_pending_review"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"TTS laboratuvarı: {error}", file=sys.stderr)
        raise SystemExit(1) from error
