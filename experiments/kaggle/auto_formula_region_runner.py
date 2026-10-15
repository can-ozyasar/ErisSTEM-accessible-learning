"""Private production batch: whole formula crop to OCR proposal, never publication."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-auto-formula-regions-v1")
OUTPUT = Path("/kaggle/working/eristem-private-formula-ocr/runs/pp-formulanet-plus-l-book-v1")
CANDIDATE = "PP-FormulaNet_plus-L"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nodes(value: object) -> Iterator[dict]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def formula_from_result(directory: Path) -> str:
    values: list[str] = []
    for path in directory.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for item in nodes(payload):
            for key, value in item.items():
                if key.lower() in {"rec_formula", "formula", "latex", "latex_text", "formula_text"} and isinstance(value, str) and value.strip():
                    values.append(value.strip())
    return values[0] if len(set(values)) == 1 else ""


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "paddleocr[doc-parser]"], check=True)
    from paddleocr import FormulaRecognitionPipeline

    manifests = list(INPUT.rglob("formula-region-manifest.json"))
    if len(manifests) != 1:
        raise RuntimeError("exactly one private formula manifest required")
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "formula-region-benchmark-input-v1":
        raise RuntimeError("formula manifest schema mismatch")
    pipeline = FormulaRecognitionPipeline(formula_recognition_model_name=CANDIDATE, engine="transformers", device="gpu")
    raw, predictions = OUTPUT / "raw", []
    raw.mkdir()
    for position, region in enumerate(manifest["regions"], start=1):
        image = INPUT / region["asset_path"]
        if not image.is_file() or digest(image) != region["asset_checksum"]:
            raise RuntimeError("formula crop checksum mismatch")
        result_dir = raw / region["id"]
        try:
            result = list(pipeline.predict(str(image), use_layout_detection=False))
            if len(result) != 1:
                raise RuntimeError("unexpected formula result count")
            result_dir.mkdir()
            result[0].save_to_json(save_path=result_dir)
            latex = formula_from_result(result_dir)
            predictions.append({"id": region["id"], "visible_notation": latex, "confidence": 0.0, "status": "completed" if latex else "no-formula"})
            print(f"[{position}/{len(manifest['regions'])}] {region['id']} completed")
        except Exception as error:  # noqa: BLE001
            predictions.append({"id": region["id"], "visible_notation": "", "confidence": 0.0, "status": "failed"})
            print(f"[{position}/{len(manifest['regions'])}] {region['id']} failed {type(error).__name__}")
    (OUTPUT / "formula_predictions.json").write_text(json.dumps({"schema_version": "formula-region-predictions-v1", "candidate": CANDIDATE, "predictions": predictions}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"regions": len(predictions), "completed": sum(item["status"] == "completed" for item in predictions)}))


if __name__ == "__main__":
    main()
