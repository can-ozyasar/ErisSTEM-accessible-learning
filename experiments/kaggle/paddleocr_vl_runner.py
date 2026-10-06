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
from collections import Counter, defaultdict
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-gold-benchmark-v1")
OUTPUT_ROOT = Path("/kaggle/working/eristem-private-paddleocr-vl")
RUN_ID = "paddleocr-vl-1.6-transformers-chart-v1"
OUTPUT = OUTPUT_ROOT / "runs" / RUN_ID


def iter_nodes(value: object):
    """Yield JSON objects without retaining document text in a derived report."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_nodes(child)


def structural_evidence(result_dir: Path) -> dict[str, int]:
    """Return content-free structural signals from PaddleOCR result JSON files."""
    evidence: Counter[str] = Counter()
    for path in result_dir.rglob("*.json"):
        evidence["result_json_files"] += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            evidence["unreadable_result_json_files"] += 1
            continue
        for node in iter_nodes(payload):
            label = str(node.get("block_label", node.get("label", ""))).lower()
            if label:
                evidence[f"label:{label}"] += 1
            content = node.get("block_content")
            if isinstance(content, str):
                evidence["content_characters"] += len(content.strip())
                evidence["latex_markers"] += sum(
                    content.count(marker)
                    for marker in ("$", "\\frac", "\\sqrt", "\\left", "\\right")
                )
                evidence["html_table_markers"] += content.lower().count("<table")
            bbox = node.get("block_bbox", node.get("coordinate"))
            if isinstance(bbox, list) and len(bbox) == 4 and all(
                isinstance(value, (int, float)) for value in bbox
            ):
                evidence["valid_bounding_boxes"] += 1
    return dict(evidence)


def has_expected_signal(kind: str, evidence: dict[str, int]) -> bool:
    if kind == "formula":
        return evidence.get("label:inline_formula", 0) + evidence.get("label:formula", 0) > 0 or evidence.get(
            "latex_markers", 0
        ) > 0
    if kind == "table":
        return evidence.get("label:table", 0) > 0 or evidence.get("html_table_markers", 0) > 0
    if kind == "chart":
        # Bir görüntü etiketi grafik doğruluğu kanıtı değildir; yalnız chart sinyali kabul edilir.
        return evidence.get("label:chart", 0) > 0
    return evidence.get("content_characters", 0) > 0


def create_structural_report(manifest: dict, records: list[dict[str, object]]) -> dict:
    """Create a private, content-free diagnostic report; this is not an accuracy score."""
    records_by_id = {str(record["id"]): record for record in records}
    by_kind: dict[str, dict[str, int]] = defaultdict(lambda: Counter(total=0, completed=0, signals=0))
    items = []
    for item in manifest["items"]:
        item_id, kind = item["id"], item["kind"]
        record = records_by_id.get(item_id, {})
        status = record.get("status", "missing")
        evidence = structural_evidence(OUTPUT / "results" / item_id) if status == "completed" else {}
        signal = status == "completed" and has_expected_signal(kind, evidence)
        by_kind[kind]["total"] += 1
        by_kind[kind]["completed"] += status == "completed"
        by_kind[kind]["signals"] += signal
        items.append(
            {
                "id": item_id,
                "kind": kind,
                "status": status,
                "expected_signal_found": signal,
                "evidence": evidence,
            }
        )
    return {
        "candidate": "paddleocr-vl",
        "report_type": "structural_proxy_not_accuracy",
        "contains_document_content": False,
        "accuracy_decision": "blocked_needs_gold_annotations",
        "by_kind": {kind: dict(values) for kind, values in by_kind.items()},
        "items": items,
    }


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
    # Aynı konfigürasyonun yarım kalmış artefact'ları ölçümü kirletmesin. Daha
    # önceki smoke-test çıktısı OUTPUT_ROOT altında, bu run kimliğinin dışında kalır.
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
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
    pipeline = PaddleOCRVL(engine="transformers", use_chart_recognition=True)
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
        "run_id": RUN_ID,
        "engine": "transformers",
        "gpu": gpu,
        "python": sys.version,
        "paddleocr_version": importlib.metadata.version("paddleocr"),
        "input_private": True,
        "pipeline_initializations": 1,
        "use_chart_recognition": True,
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
    report = create_structural_report(manifest, records)
    (OUTPUT / "structural_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.rmtree(pages_dir)
    completed = sum(record["status"] == "completed" for record in records)
    signals = sum(item["expected_signal_found"] for item in report["items"])
    print(
        f"Bitti: {completed}/{total} tamamlandı; beklenen yapı sinyali {signals}/{total}. "
        f"Özet: {OUTPUT / 'structural_report.json'}"
    )


if __name__ == "__main__":
    main()
