"""Safe, auditable Kaggle private-Dataset operations for ErişSTEM.

No command uploads by default. A remote mutation needs both ``upload-dataset``
and ``--apply``. Credentials are read only by kagglehub from the local user
credential store; this script never reads, prints, or writes a token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

HANDLE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$")


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


def main() -> int:
    parser = argparse.ArgumentParser(description="ErişSTEM safe Kaggle private-Dataset operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="Yalnız Kaggle kimlik doğrulamasını denetler")
    for name in ("prepare-dataset", "upload-dataset"):
        command = commands.add_parser(name)
        command.add_argument("--source-dir", type=Path, required=True)
        command.add_argument("--handle", required=True)
        command.add_argument("--version-notes", required=True)
        if name == "upload-dataset":
            command.add_argument("--apply", action="store_true", help="Uzak Dataset sürümü oluşturmayı açıkça onaylar")
    args = parser.parse_args()
    if args.command == "verify":
        print(json.dumps(verify(), ensure_ascii=False))
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
