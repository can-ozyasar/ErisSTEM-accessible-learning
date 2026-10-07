"""Private Kaggle T4 runner for a sealed mathematical symbol-cell benchmark.

Expected answers are deliberately absent from INPUT. Predictions remain in the
private notebook output and are only scored against local private Gold.
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

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-symbol-cell-benchmark-v1")
OUTPUT = Path("/kaggle/working/eristem-private-symbol-cell-paddleocr-v1")
MANIFEST_NAME = "symbol-cell-manifest.json"
PREDICTIONS_NAME = "symbol_predictions.json"
MAX_PREDICTION_CHARS = 128


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_manifest() -> tuple[Path, dict]:
    manifests = list(INPUT.rglob(MANIFEST_NAME))
    if not manifests and list(INPUT.rglob("*.zip")):
        unpacked = OUTPUT / "input"
        with zipfile.ZipFile(next(INPUT.rglob("*.zip"))) as archive:
            archive.extractall(unpacked)
        manifests = list(unpacked.rglob(MANIFEST_NAME))
    if len(manifests) != 1:
        raise RuntimeError("Private input içinde tam bir symbol-cell manifest bulunmalı")
    manifest_path = manifests[0]
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "symbol-cell-benchmark-input-v1" or not isinstance(payload.get("assets"), list):
        raise RuntimeError("Symbol-cell input şeması geçersiz")
    if "expected" in payload:
        raise RuntimeError("Aday input paketi expected cevaplarını içeremez")
    return manifest_path, payload


def asset_path(manifest_path: Path, relative_path: str) -> Path:
    root = manifest_path.parent.resolve()
    declared = Path(relative_path)
    if declared.is_absolute() or ".." in declared.parts:
        raise RuntimeError("Asset yolu izinli paketin dışında")
    asset = (root / declared).resolve()
    if not asset.is_relative_to(root) or not asset.is_file():
        raise RuntimeError("Asset eksik veya izinli paketin dışında")
    return asset


def iter_strings(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"rec_text", "text"} and isinstance(child, str):
                yield child
            elif key == "rec_texts" and isinstance(child, list):
                yield from (item for item in child if isinstance(item, str))
            else:
                yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)


def prediction_from_result(result_dir: Path) -> str:
    values = []
    for path in result_dir.rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        values.extend(value.strip() for value in iter_strings(payload) if value.strip())
    unique = list(dict.fromkeys(values))
    if len(unique) != 1 or len(unique[0]) > MAX_PREDICTION_CHARS:
        return ""
    return unique[0]


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    gpu = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=name,compute_cap,driver_version", "--format=csv,noheader"], text=True
    ).strip()
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "paddleocr[doc-parser]"], check=True)
    from paddleocr import PaddleOCRVL

    manifest_path, manifest = resolve_manifest()
    pipeline = PaddleOCRVL(engine="transformers")
    predictions, records = [], []
    results = OUTPUT / "private-results"
    for index, asset in enumerate(manifest["assets"], start=1):
        asset_id = asset.get("id")
        image = asset_path(manifest_path, str(asset.get("asset_path", "")))
        if not isinstance(asset_id, str) or sha256(image) != asset.get("asset_checksum"):
            raise RuntimeError("Asset kimliği veya checksum geçersiz")
        print(f"[{index}/{len(manifest['assets'])}] İşleniyor: {asset_id}")
        try:
            result_dir = results / asset_id
            result_dir.mkdir(parents=True, exist_ok=True)
            output = list(pipeline.predict(str(image)))
            if len(output) != 1:
                raise RuntimeError("Beklenmeyen model çıktısı")
            output[0].save_to_json(save_path=result_dir)
            prediction = prediction_from_result(result_dir)
            status = "completed" if prediction else "no-text"
            predictions.append({"id": asset_id, "prediction": prediction, "status": status})
            records.append({"id": asset_id, "status": status})
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
            predictions.append({"id": asset_id, "prediction": "", "status": "failed"})
            records.append({"id": asset_id, "status": "failed"})
    # Kaggle downloads only /kaggle/working root outputs reliably. Keep raw
    # inference files in OUTPUT, but expose this schema-limited private file.
    (Path("/kaggle/working") / PREDICTIONS_NAME).write_text(
        json.dumps({"schema_version": "symbol-cell-predictions-v1", "candidate": "paddleocr-vl-transformers", "predictions": predictions}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT / "run_metadata.json").write_text(
        json.dumps({"candidate": "paddleocr-vl-transformers", "paddleocr_version": importlib.metadata.version("paddleocr"), "gpu": gpu, "input_private": True}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT / "run_records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(OUTPUT / "input", ignore_errors=True)
    print(f"Bitti: {sum(item['status'] == 'completed' for item in records)}/{len(records)} tahmin üretildi; yayın kapalı.")


if __name__ == "__main__":
    main()
