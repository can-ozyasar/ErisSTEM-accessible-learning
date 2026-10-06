"""Kaggle T4: private MEB Gold sayfalarında PaddleOCR-VL karşılaştırması.

Bu betik yalnız private Kaggle notebook'ta çalışır. Ham PDF'yi veya türetilmiş
çıktıları dışa aktarmak yerine, her sayfanın private artefact yolunu ve checksum'ını
kaydeder. T4 (CC 7.5) üzerinde vLLM yerine resmi Transformers motorunu kullanır.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-gold-benchmark-v1")
OUTPUT = Path("/kaggle/working/eristem-private-paddleocr-vl")
PAGE_TIMEOUT_SECONDS = 900


def run(command: list[str], *, timeout: int | None = None) -> None:
    subprocess.run(command, check=True, timeout=timeout)


def command_output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()


def resolve_inputs() -> tuple[Path, Path]:
    pdfs = list(INPUT.rglob("*.pdf"))
    manifests = list(INPUT.rglob("gold-v1.json"))
    if not pdfs and list(INPUT.rglob("*.zip")):
        unpacked = OUTPUT / "input"
        with zipfile.ZipFile(next(INPUT.rglob("*.zip"))) as source:
            source.extractall(unpacked)
        pdfs = list(unpacked.rglob("*.pdf"))
        manifests = list(unpacked.rglob("gold-v1.json"))
    if len(pdfs) != 1 or len(manifests) != 1:
        raise RuntimeError("Private input içinde tam bir PDF ve gold-v1.json bulunmalı")
    return pdfs[0], manifests[0]


def page_pdf(source: Path, page_number: int, destination: Path) -> None:
    import pymupdf

    with pymupdf.open(source) as input_pdf:
        output = pymupdf.open()
        output.insert_pdf(input_pdf, from_page=page_number - 1, to_page=page_number - 1)
        output.save(destination)
        output.close()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artefacts_for(result_dir: Path) -> list[dict[str, str | int]]:
    return [
        {
            "path": str(path.relative_to(OUTPUT)),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(result_dir.rglob("*"))
        if path.is_file()
    ]


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    run(["nvidia-smi"])
    gpu = command_output(
        ["nvidia-smi", "--query-gpu=name,compute_cap,driver_version", "--format=csv,noheader"]
    )

    # PaddleOCR-VL'nin ilk model indirmesi Internet açıkken yapılır. Bu komut
    # PaddlePaddle CPU/GPU paketini zorla kurmaz; T4'te resmi Transformers motoru
    # seçildiği için Kaggle'in mevcut CUDA/PyTorch ortamıyla çalışır.
    run([sys.executable, "-m", "pip", "install", "--quiet", "pymupdf", "paddleocr[doc-parser]"])
    run(["paddleocr", "--help"])

    pdf, manifest_path = resolve_inputs()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages_dir = OUTPUT / "pages"
    results_dir = OUTPUT / "results"
    pages_dir.mkdir(exist_ok=True)
    results_dir.mkdir(exist_ok=True)
    records: list[dict[str, object]] = []

    for item in manifest["items"]:
        item_id = item["id"]
        one_page = pages_dir / f"{item_id}.pdf"
        result_dir = results_dir / item_id
        page_pdf(pdf, item["page"], one_page)
        command = [
            "paddleocr",
            "doc_parser",
            "-i",
            str(one_page),
            "--engine",
            "transformers",
            "--save_path",
            str(result_dir),
        ]
        try:
            run(command, timeout=PAGE_TIMEOUT_SECONDS)
            records.append(
                {
                    "id": item_id,
                    "page": item["page"],
                    "kind": item["kind"],
                    "status": "completed",
                    "artefacts": artefacts_for(result_dir),
                }
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            records.append(
                {
                    "id": item_id,
                    "page": item["page"],
                    "kind": item["kind"],
                    "status": "failed",
                    "error": str(error),
                }
            )

    metadata = {
        "candidate": "paddleocr-vl",
        "engine": "transformers",
        "gpu": gpu,
        "python": sys.version,
        "paddleocr_version": importlib.metadata.version("paddleocr"),
        "input_private": True,
        "page_timeout_seconds": PAGE_TIMEOUT_SECONDS,
        "metric_status": (
            "ready_to_score" if all(item.get("expected") for item in manifest["items"])
            else "blocked_missing_gold_annotations"
        ),
    }
    (OUTPUT / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUTPUT / "run_records.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.rmtree(pages_dir)


if __name__ == "__main__":
    main()
