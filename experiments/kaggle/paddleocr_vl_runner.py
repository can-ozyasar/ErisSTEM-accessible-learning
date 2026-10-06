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
    gpu = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=name,compute_cap,driver_version", "--format=csv,noheader"],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()

    # PaddleOCR-VL'nin ilk model indirmesi Internet açıkken yapılır. Bu komut
    # PaddlePaddle CPU/GPU paketini zorla kurmaz; T4'te resmi Transformers motoru
    # seçildiği için Kaggle'in mevcut CUDA/PyTorch ortamıyla çalışır.
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "pymupdf", "paddleocr[doc-parser]"],
        check=True,
    )
    from paddleocr import PaddleOCRVL

    pdf, manifest_path = resolve_inputs()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages_dir = OUTPUT / "pages"
    results_dir = OUTPUT / "results"
    pages_dir.mkdir(exist_ok=True)
    results_dir.mkdir(exist_ok=True)
    records: list[dict[str, object]] = []
    total = len(manifest["items"])

    # Komut satırı aracı sayfa başına yeni bir süreç/model kurar. Resmi Python
    # API'si modeli bir kez GPU'ya alır; aşağıdaki tüm sayfalar aynı pipeline'ı
    # kullanır. Bu, benchmark'ın hem daha hızlı hem de tekrar üretilebilir olmasını sağlar.
    pipeline = PaddleOCRVL(engine="transformers")
    print(f"PaddleOCR-VL hazır. {total} private Gold örneği işlenecek; model bir kez yüklendi.")

    for position, item in enumerate(manifest["items"], start=1):
        item_id = item["id"]
        one_page = pages_dir / f"{item_id}.pdf"
        result_dir = results_dir / item_id
        page_pdf(pdf, item["page"], one_page)
        print(f"[{position}/{total}] İşleniyor: {item_id} ({item['kind']}, PDF sayfası {item['page']})")
        try:
            # Tek sayfalık PDF'nin sonucu tek bir PaddleOCRVLResult olur. JSON ve
            # Markdown private result_dir altında tutulur; terminale ham içerik yazılmaz.
            outputs = list(pipeline.predict(str(one_page)))
            if len(outputs) != 1:
                raise RuntimeError(f"{item_id} için beklenmeyen çıktı sayısı: {len(outputs)}")
            result_dir.mkdir(parents=True, exist_ok=True)
            outputs[0].save_to_json(save_path=result_dir)
            outputs[0].save_to_markdown(save_path=result_dir)
            records.append(
                {
                    "id": item_id,
                    "page": item["page"],
                    "kind": item["kind"],
                    "status": "completed",
                    "artefacts": artefacts_for(result_dir),
                }
            )
            print(f"[{position}/{total}] Tamamlandı: {item_id}")
        except Exception as error:  # Her Gold örneği diğerlerinden bağımsız kayda geçer.
            records.append(
                {
                    "id": item_id,
                    "page": item["page"],
                    "kind": item["kind"],
                    "status": "failed",
                    "error": str(error),
                }
            )
            print(f"[{position}/{total}] Başarısız: {item_id} ({type(error).__name__})")

    metadata = {
        "candidate": "paddleocr-vl",
        "engine": "transformers",
        "gpu": gpu,
        "python": sys.version,
        "paddleocr_version": importlib.metadata.version("paddleocr"),
        "input_private": True,
        "pipeline_initializations": 1,
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
    completed = sum(record["status"] == "completed" for record in records)
    print(f"Bitti: {completed}/{total} tamamlandı. Özet: {OUTPUT / 'run_metadata.json'}")


if __name__ == "__main__":
    main()
