"""Safe, auditable Kaggle private Dataset and Notebook operations for ErişSTEM.

No command uploads or starts a Notebook by default. A remote mutation needs an
``--apply`` flag. Credentials are read only by Kaggle clients from the local
user credential store; this script never reads, prints, or writes a token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HANDLE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$")
SUMMARY_FILENAMES = (
    "run_metadata.json",
    "run_records.json",
    "structural_report.json",
    "region_records.json",
    "native_agreement_report.json",
)
SYMBOL_PREDICTIONS_FILENAME = "symbol_predictions.json"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def private_root() -> Path:
    return (repo_root() / "data" / "private").resolve()


def private_directory(value: Path) -> Path:
    path = value.resolve()
    root = private_root()
    if not path.is_relative_to(root) or not path.is_dir():
        raise ValueError("Dataset kaynağı yalnız data/private altındaki bir klasör olabilir")
    return path


def private_path(value: Path) -> Path:
    """Accept a non-existing path only when it remains below data/private."""
    path = value.resolve()
    if not path.is_relative_to(private_root()):
        raise ValueError("İşlem yolu yalnız data/private altında olabilir")
    return path


def validate_handle(handle: str) -> str:
    if not HANDLE_PATTERN.fullmatch(handle):
        raise ValueError("Kaggle handle 'kullanici/dataset' biçiminde olmalı")
    return handle


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_manifest(source: Path) -> list[dict[str, str | int]]:
    root = private_directory(source)
    return [
        {
            "path": str(path.relative_to(root)),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def write_record(action: str, handle: str, source: Path, *, applied: bool, version_notes: str) -> Path:
    directory = private_root() / "kaggle-operation-records"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    record = {
        "schema_version": "kaggle-operation-record-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "action": action,
        "dataset_handle": validate_handle(handle),
        "source_relative_path": str(private_directory(source).relative_to(private_root())),
        "applied": applied,
        "version_notes": version_notes,
        "files": dataset_manifest(source),
    }
    destination = directory / f"{timestamp}-{action}.json"
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def write_notebook_record(
    action: str,
    kernel: str,
    dataset: str,
    package: Path,
    *,
    applied: bool,
    details: dict[str, object] | None = None,
) -> Path:
    """Record orchestration metadata without reading raw document outputs."""
    directory = private_root() / "kaggle-operation-records"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    package = private_directory(package)
    record = {
        "schema_version": "kaggle-notebook-operation-record-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "action": action,
        "kernel": validate_handle(kernel),
        "dataset_handle": validate_handle(dataset),
        "package_relative_path": str(package.relative_to(private_root())),
        "applied": applied,
        "files": dataset_manifest(package),
        "details": details or {},
    }
    destination = directory / f"{timestamp}-{action}.json"
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def kagglehub_client():
    try:
        import kagglehub
    except ImportError as exc:
        raise RuntimeError("kagglehub kurulu değil; güvenli yerel venv içinde yükleyin") from exc
    return kagglehub


def verify() -> dict[str, str]:
    user = kagglehub_client().whoami().get("username")
    if not isinstance(user, str) or not user:
        raise RuntimeError("Kaggle kimlik doğrulaması kullanıcı adı döndürmedi")
    return {"authenticated_user": user}


def upload_dataset(source: Path, handle: str, version_notes: str) -> None:
    kagglehub_client().dataset_upload(validate_handle(handle), str(private_directory(source)), version_notes=version_notes)


def runner_path(value: Path) -> Path:
    """Permit only checked-in Kaggle runner source, never an arbitrary local script."""
    path = value.resolve()
    allowed_root = (repo_root() / "experiments" / "kaggle").resolve()
    if not path.is_relative_to(allowed_root) or not path.is_file() or path.suffix != ".py":
        raise ValueError("Notebook runner yalnız experiments/kaggle altındaki bir .py dosyası olabilir")
    return path


def kernel_package_directory(kernel: str) -> Path:
    owner, slug = validate_handle(kernel).split("/", maxsplit=1)
    return private_root() / "kaggle-notebooks" / owner / slug


def prepare_notebook_package(
    kernel: str,
    dataset: str,
    runner: Path,
    title: str,
    *,
    enable_internet: bool,
) -> Path:
    """Create a private Kaggle script package, refusing to overwrite a package."""
    kernel, dataset = validate_handle(kernel), validate_handle(dataset)
    source = runner_path(runner)
    if dataset not in source.read_text(encoding="utf-8"):
        raise ValueError("Runner içindeki private Dataset yolu --dataset ile eşleşmiyor")
    package = kernel_package_directory(kernel)
    if package.exists():
        raise FileExistsError("Notebook paketi zaten var; önce içeriği inceleyip bilinçli olarak kaldırın")
    package.mkdir(parents=True)
    shutil.copy2(source, package / "run.py")
    metadata = {
        "id": kernel,
        "title": title,
        "code_file": "run.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": "true",
        "enable_gpu": "true",
        "enable_internet": "true" if enable_internet else "false",
        "dataset_sources": [dataset],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    (package / "kernel-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return package


def load_kernel_metadata(package: Path, kernel: str, dataset: str) -> dict[str, object]:
    package = private_directory(package)
    metadata_path = package / "kernel-metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Notebook metadata dosyası okunamadı") from exc
    if not isinstance(metadata, dict):
        raise TypeError("Notebook metadata nesne olmalı")
    if metadata.get("id") != validate_handle(kernel) or metadata.get("is_private") != "true":
        raise ValueError("Notebook handle veya private ayarı doğrulanamadı")
    if metadata.get("dataset_sources") != [validate_handle(dataset)]:
        raise ValueError("Notebook Dataset kaynağı doğrulanamadı")
    code_file = metadata.get("code_file")
    if not isinstance(code_file, str) or not (package / code_file).is_file():
        raise ValueError("Notebook code_file pakette bulunamadı")
    return metadata


def kaggle_cli() -> str:
    local = Path(sys.executable).with_name("kaggle")
    if local.is_file():
        return str(local)
    executable = shutil.which("kaggle")
    if not executable:
        raise RuntimeError("Kaggle CLI kurulu değil; apps/api/.venv içinde kaggle paketini yükleyin")
    return executable


def run_cli(arguments: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [kaggle_cli(), *arguments], check=True, text=True, capture_output=capture_output
    )


def push_notebook(package: Path, kernel: str, dataset: str, timeout: int, accelerator: str) -> None:
    load_kernel_metadata(package, kernel, dataset)
    run_cli(
        [
            "kernels",
            "push",
            "--path",
            str(private_directory(package)),
            "--timeout",
            str(timeout),
            "--accelerator",
            accelerator,
        ]
    )


def notebook_status(kernel: str) -> str:
    result = run_cli(["kernels", "status", validate_handle(kernel)], capture_output=True)
    return result.stdout.strip()


def output_directory(kernel: str) -> Path:
    owner, slug = validate_handle(kernel).split("/", maxsplit=1)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = private_root() / "kaggle-notebook-outputs" / owner / slug / timestamp
    destination.mkdir(parents=True)
    return destination


def download_summaries(kernel: str) -> tuple[Path, list[dict[str, object]]]:
    """Download only explicit content-free report filenames to a fresh private folder."""
    destination = output_directory(kernel)
    results: list[dict[str, object]] = []
    for filename in SUMMARY_FILENAMES:
        result = subprocess.run(
            [
                kaggle_cli(),
                "kernels",
                "output",
                validate_handle(kernel),
                "--path",
                str(destination),
                "--force",
                "--quiet",
                "--file-pattern",
                f"^{re.escape(filename)}$",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        results.append({"filename": filename, "downloaded": result.returncode == 0})
    downloaded = [path for path in destination.rglob("*") if path.is_file()]
    unexpected = [path.name for path in downloaded if path.name not in SUMMARY_FILENAMES]
    if unexpected:
        raise RuntimeError("İndirme allowlist dışı dosya üretti: " + ", ".join(sorted(unexpected)))
    manifest = [
        {"path": str(path.relative_to(destination)), "sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(downloaded)
    ]
    (destination / "download_manifest.json").write_text(
        json.dumps({"kernel": validate_handle(kernel), "files": manifest, "attempts": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination, results


def symbol_input_ids(input_manifest: Path) -> set[str]:
    """Read IDs only from the sealed candidate manifest; never read local Gold."""
    path = private_path(input_manifest)
    if not path.is_file():
        raise ValueError("Symbol input manifesti private dosya olarak bulunamadı")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assets = payload["assets"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Symbol input manifesti okunamadı") from exc
    if payload.get("schema_version") != "symbol-cell-benchmark-input-v1" or not isinstance(assets, list):
        raise ValueError("Symbol input şeması geçersiz")
    ids = {item.get("id") for item in assets if isinstance(item, dict) and isinstance(item.get("id"), str)}
    if not ids or len(ids) != len(assets) or "expected" in payload:
        raise ValueError("Symbol input manifesti aday benchmark sınırını karşılamıyor")
    return ids


def validate_symbol_predictions(path: Path, expected_ids: set[str]) -> None:
    """Reject arbitrary notebook output before it enters the private evaluation path."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        predictions = payload["predictions"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Symbol prediction dosyası okunamadı") from exc
    if (
        set(payload) != {"schema_version", "candidate", "predictions"}
        or payload.get("schema_version") != "symbol-cell-predictions-v1"
        or not isinstance(payload.get("candidate"), str)
        or not 1 <= len(payload["candidate"]) <= 80
        or not isinstance(predictions, list)
    ):
        raise ValueError("Symbol prediction şeması geçersiz")
    seen: set[str] = set()
    for item in predictions:
        if not isinstance(item, dict) or set(item) != {"id", "prediction", "status"}:
            raise ValueError("Symbol prediction alanları geçersiz")
        asset_id, prediction, status = item.get("id"), item.get("prediction"), item.get("status")
        if (
            not isinstance(asset_id, str)
            or asset_id not in expected_ids
            or asset_id in seen
            or not isinstance(prediction, str)
            or len(prediction) > 128
            or status not in {"completed", "no-text", "failed"}
        ):
            raise ValueError("Symbol prediction kaydı geçersiz")
        seen.add(asset_id)
    if seen != expected_ids:
        raise ValueError("Symbol prediction kayıtları aday input hücreleriyle eşleşmiyor")


def download_symbol_predictions(kernel: str, input_manifest: Path) -> Path:
    """Download exactly one schema-checked private prediction file for local scoring."""
    expected_ids = symbol_input_ids(input_manifest)
    destination = output_directory(kernel)
    result = subprocess.run(
        [
            kaggle_cli(),
            "kernels",
            "output",
            validate_handle(kernel),
            "--path",
            str(destination),
            "--force",
            "--quiet",
            "--file-pattern",
            f"^{re.escape(SYMBOL_PREDICTIONS_FILENAME)}$",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    prediction_files = [path for path in destination.rglob(SYMBOL_PREDICTIONS_FILENAME) if path.is_file()]
    unexpected = [path.name for path in destination.rglob("*") if path.is_file() and path.name != SYMBOL_PREDICTIONS_FILENAME]
    if result.returncode != 0 or len(prediction_files) != 1 or unexpected:
        raise RuntimeError("Yalnız izinli symbol prediction dosyası indirilemedi")
    predictions = prediction_files[0]
    validate_symbol_predictions(predictions, expected_ids)
    manifest = {
        "schema_version": "kaggle-symbol-prediction-download-v1",
        "kernel": validate_handle(kernel),
        "input_manifest_relative_path": str(private_path(input_manifest).relative_to(private_root())),
        "files": [{"path": str(predictions.relative_to(destination)), "sha256": sha256(predictions), "bytes": predictions.stat().st_size}],
    }
    (destination / "download_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return predictions


def main() -> int:
    parser = argparse.ArgumentParser(description="ErişSTEM safe Kaggle private Dataset and Notebook operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="Yalnız Kaggle kimlik doğrulamasını denetler")
    for name in ("prepare-dataset", "upload-dataset"):
        command = commands.add_parser(name)
        command.add_argument("--source-dir", type=Path, required=True)
        command.add_argument("--handle", required=True)
        command.add_argument("--version-notes", required=True)
        if name == "upload-dataset":
            command.add_argument("--apply", action="store_true", help="Uzak Dataset sürümü oluşturmayı açıkça onaylar")
    package = commands.add_parser("prepare-notebook", help="Private Kaggle script paketini yalnız yerelde oluşturur")
    package.add_argument("--kernel", required=True)
    package.add_argument("--dataset", required=True)
    package.add_argument("--runner", type=Path, required=True)
    package.add_argument("--title", required=True)
    package.add_argument("--internet", action="store_true", help="Yalnız model/paket indirmesi gerektiğinde etkinleştir")
    push = commands.add_parser("push-notebook", help="Private paketi Kaggle'a gönderir ve koşumu başlatır")
    push.add_argument("--package-dir", type=Path, required=True)
    push.add_argument("--kernel", required=True)
    push.add_argument("--dataset", required=True)
    push.add_argument("--timeout", type=int, default=3600)
    push.add_argument("--accelerator", default="NvidiaTeslaT4")
    push.add_argument("--apply", action="store_true", help="Uzak private Notebook oluşturma/güncelleme ve koşumu açıkça onaylar")
    status = commands.add_parser("notebook-status", help="Notebook durumunu yalnız-okunur sorgular")
    status.add_argument("--kernel", required=True)
    output = commands.add_parser("download-summaries", help="Yalnız izinli içeriksiz özet JSON'larını indirir")
    output.add_argument("--kernel", required=True)
    predictions = commands.add_parser(
        "download-symbol-predictions", help="Yalnız şema-doğrulanmış private sembol tahminlerini indirir"
    )
    predictions.add_argument("--kernel", required=True)
    predictions.add_argument("--input-manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        print(json.dumps(verify(), ensure_ascii=False))
        return 0
    if args.command == "notebook-status":
        print(json.dumps({"kernel": validate_handle(args.kernel), "status": notebook_status(args.kernel)}, ensure_ascii=False))
        return 0
    if args.command == "prepare-notebook":
        package = prepare_notebook_package(args.kernel, args.dataset, args.runner, args.title, enable_internet=args.internet)
        record = write_notebook_record("prepare-notebook", args.kernel, args.dataset, package, applied=False)
        print(json.dumps({"status": "prepared-not-pushed", "package": str(package), "record": str(record)}, ensure_ascii=False))
        return 0
    if args.command == "push-notebook":
        package = private_directory(args.package_dir)
        load_kernel_metadata(package, args.kernel, args.dataset)
        if not args.apply:
            record = write_notebook_record("push-notebook", args.kernel, args.dataset, package, applied=False, details={"timeout": args.timeout, "accelerator": args.accelerator})
            print(json.dumps({"status": "dry-run-not-pushed", "record": str(record)}, ensure_ascii=False))
            return 0
        push_notebook(package, args.kernel, args.dataset, args.timeout, args.accelerator)
        record = write_notebook_record("push-notebook", args.kernel, args.dataset, package, applied=True, details={"timeout": args.timeout, "accelerator": args.accelerator})
        print(json.dumps({"status": "pushed-and-started", "record": str(record)}, ensure_ascii=False))
        return 0
    if args.command == "download-summaries":
        destination, attempts = download_summaries(args.kernel)
        print(json.dumps({"status": "download-complete", "output": str(destination), "attempts": attempts}, ensure_ascii=False))
        return 0
    if args.command == "download-symbol-predictions":
        prediction_path = download_symbol_predictions(args.kernel, args.input_manifest)
        print(json.dumps({"status": "download-complete", "predictions": str(prediction_path)}, ensure_ascii=False))
        return 0
    source, handle = private_directory(args.source_dir), validate_handle(args.handle)
    if args.command == "prepare-dataset":
        record = write_record("prepare-dataset", handle, source, applied=False, version_notes=args.version_notes)
        print(json.dumps({"status": "prepared-not-uploaded", "record": str(record)}, ensure_ascii=False))
        return 0
    if not args.apply:
        record = write_record("upload-dataset", handle, source, applied=False, version_notes=args.version_notes)
        print(json.dumps({"status": "dry-run-not-uploaded", "record": str(record)}, ensure_ascii=False))
        return 0
    upload_dataset(source, handle, args.version_notes)
    record = write_record("upload-dataset", handle, source, applied=True, version_notes=args.version_notes)
    print(json.dumps({"status": "uploaded", "record": str(record)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
