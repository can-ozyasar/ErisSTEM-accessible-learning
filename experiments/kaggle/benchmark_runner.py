"""Kaggle T4: private MEB Gold sayfalarında Docling baseline deneyi."""

from __future__ import annotations

import importlib.metadata
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pymupdf

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-gold-benchmark-v1")
OUTPUT = Path("/kaggle/working/eristem-private-benchmark")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def resolve_inputs() -> tuple[Path, Path]:
    pdfs, manifests = list(INPUT.rglob("*.pdf")), list(INPUT.rglob("gold-v1.json"))
    if not pdfs and list(INPUT.rglob("*.zip")):
        unpacked = OUTPUT / "input"
        with zipfile.ZipFile(next(INPUT.rglob("*.zip"))) as source:
            source.extractall(unpacked)
        pdfs, manifests = list(unpacked.rglob("*.pdf")), list(unpacked.rglob("gold-v1.json"))
    if len(pdfs) != 1 or len(manifests) != 1:
        raise RuntimeError("Private input içinde tam bir PDF ve gold-v1.json bulunmalı")
    return pdfs[0], manifests[0]


def page_pdf(source: Path, page_number: int, destination: Path) -> None:
    with pymupdf.open(source) as input_pdf:
        output = pymupdf.open()
        output.insert_pdf(input_pdf, from_page=page_number - 1, to_page=page_number - 1)
        output.save(destination)
        output.close()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    run(["nvidia-smi"])
    run(["python", "-m", "pip", "install", "--quiet", "docling"])
    from docling.document_converter import DocumentConverter

    pdf, manifest_path = resolve_inputs()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    converter = DocumentConverter()
    pages_dir = OUTPUT / "pages"
    pages_dir.mkdir(exist_ok=True)
    predictions = []
    for item in manifest["items"]:
        one_page = pages_dir / f"{item['id']}.pdf"
        page_pdf(pdf, item["page"], one_page)
        result = converter.convert(str(one_page))
        predictions.append({"id": item["id"], "page": item["page"], "kind": item["kind"], "markdown": result.document.export_to_markdown()})
    (OUTPUT / "docling_predictions.json").write_text(json.dumps(predictions, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "run_metadata.json").write_text(json.dumps({"candidate": "docling", "docling_version": importlib.metadata.version("docling"), "input_private": True, "metric_status": "ready_to_score" if all(item.get("expected") for item in manifest["items"]) else "blocked_missing_gold_annotations"}, indent=2), encoding="utf-8")
    shutil.rmtree(pages_dir)


if __name__ == "__main__":
    main()
