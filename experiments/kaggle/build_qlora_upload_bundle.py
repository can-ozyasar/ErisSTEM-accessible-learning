"""Create two safe Kaggle upload folders for the source-bound QLoRA pilot.

The data folder contains only train/dev JSONL plus its manifest.  The code
folder contains the runner and notebook.  Sealed evaluation data, PDF files,
answer labels and source coordinates are rejected before any copy happens.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


FORBIDDEN = ("answer_label", "answer_key", "sealed_test", "source_text", "bbox", '"page"', ".pdf")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Dosya okunamadı: {path}") from error


def _safe_jsonl(path: Path) -> None:
    text = _read(path)
    if not text.strip():
        raise ValueError(f"Boş QLoRA dosyası: {path.name}")
    for line_no, line in enumerate(text.splitlines(), start=1):
        row = json.loads(line)
        if set(row) != {"group_id", "case", "error_type", "prompt", "completion"}:
            raise ValueError(f"Beklenmeyen QLoRA alanı: {path.name}:{line_no}")
    lowered = text.casefold()
    if any(value in lowered for value in FORBIDDEN):
        raise ValueError(f"Yasak private alan bulundu: {path.name}")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(input_dir: Path, output_dir: Path, runner: Path, notebook: Path) -> dict:
    train, dev, manifest = (input_dir / "train.jsonl", input_dir / "dev.jsonl", input_dir / "manifest.json")
    for path in (train, dev, manifest, runner, notebook):
        if not path.is_file():
            raise ValueError(f"Gerekli dosya yok: {path}")
    _safe_jsonl(train)
    _safe_jsonl(dev)
    manifest_data = json.loads(_read(manifest))
    if (manifest_data.get("schema") != "eristem-tutor-qlora-experiment-input-v1"
            or manifest_data.get("answer_keys_included") is not False
            or manifest_data.get("sealed_test_uploaded") is not False
            or manifest_data.get("student_data_included") is not False):
        raise ValueError("Kaggle manifesti kapalı test veya cevap anahtarı güvenliğini doğrulamıyor")
    data_out, code_out = output_dir / "history-tutor-qlora-input-v1", output_dir / "history-tutor-code-v1"
    data_out.mkdir(parents=True, exist_ok=True)
    code_out.mkdir(parents=True, exist_ok=True)
    for source in (train, dev, manifest):
        shutil.copy2(source, data_out / source.name)
    shutil.copy2(runner, code_out / runner.name)
    shutil.copy2(notebook, code_out / notebook.name)
    return {
        "schema": "kaggle-qlora-upload-bundle-v1",
        "data_dataset": data_out.name,
        "code_dataset": code_out.name,
        "files": {str(path.relative_to(output_dir)): _digest(path) for path in (*data_out.iterdir(), *code_out.iterdir())},
        "sealed_test_included": False,
        "answer_keys_included": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--notebook", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.input_dir, args.output_dir, args.runner, args.notebook)
    (args.output_dir / "upload-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
