"""Private visual-layout probe for inline and table mathematics on whole pages."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-formula-layout-probe-v1")
OUTPUT = Path("/kaggle/working/eristem-private-layout-probe/runs/pp-formula-layout-v1")
CANDIDATE = "PP-FormulaNet_plus-L-with-layout"


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


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "paddleocr[doc-parser]"], check=True)
    from paddleocr import FormulaRecognitionPipeline

    manifests = list(INPUT.rglob("page-manifest.json"))
    if len(manifests) != 1:
        raise RuntimeError("exactly one page manifest required")
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "formula-layout-probe-v1":
        raise RuntimeError("layout probe schema mismatch")
    pipeline = FormulaRecognitionPipeline(formula_recognition_model_name="PP-FormulaNet_plus-L", engine="transformers", device="gpu")
    raw, summary = OUTPUT / "raw", []
    raw.mkdir()
    for item in manifest["pages"]:
        image = INPUT / item["asset_path"]
        if not image.is_file() or digest(image) != item["asset_checksum"]:
            raise RuntimeError("page image checksum mismatch")
        target = raw / f"page-{item['page']}"
        try:
            results = list(pipeline.predict(str(image), use_layout_detection=True))
            target.mkdir()
            for position, result in enumerate(results):
                result.save_to_json(save_path=target, base_filename=f"result-{position}")
            formula_nodes = 0
            for path in target.rglob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                formula_nodes += sum(1 for node in nodes(payload) if any(key.lower() in {"rec_formula", "formula", "latex"} for key in node))
            summary.append({"page": item["page"], "status": "completed", "formula_nodes": formula_nodes})
            print(f"page {item['page']} completed")
        except Exception as error:  # noqa: BLE001
            summary.append({"page": item["page"], "status": "failed", "formula_nodes": 0})
            print(f"page {item['page']} failed {type(error).__name__}")
    (OUTPUT / "layout_probe_summary.json").write_text(json.dumps({"report_type": "formula-layout-probe-v1", "candidate": CANDIDATE, "pages": summary}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
