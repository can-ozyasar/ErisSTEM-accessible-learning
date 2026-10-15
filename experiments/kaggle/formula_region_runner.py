"""Private Kaggle T4 benchmark for whole mathematical-expression crops.

The input Dataset must contain ``formula-region-manifest.json`` and an ``images``
directory produced from source-bound PDF rectangles.  Its separate private Gold
file is used only after inference to make a content-free report.  No source PDF,
crop, expected expression, or model LaTeX is printed to the notebook log.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-formula-regions-v1")
OUTPUT = Path("/kaggle/working/eristem-private-formula-ocr/runs/pp-formulanet-plus-l-v1")
CANDIDATE = "PP-FormulaNet_plus-L"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nodes(value: object) -> Iterator[dict]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def saved_result_notation(directory: Path) -> str:
    """Read one formula string from Paddle's private structured output.

    The public API promises structured JSON, but field names differ slightly by
    PaddleOCR release.  This deliberately accepts only explicit formula/LaTeX
    keys and returns empty rather than guessing from arbitrary OCR text.
    """
    keys = {"rec_formula", "formula", "latex", "latex_text", "formula_text"}
    candidates: list[str] = []
    for path in directory.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for node in nodes(payload):
            for key, value in node.items():
                if key.lower() in keys and isinstance(value, str) and value.strip():
                    candidates.append(value.strip())
    return candidates[0] if len(set(candidates)) == 1 else ""


def canonical(value: str) -> str:
    aliases = {
        r"\sqrt": "√", r"\cdot": "×", r"\times": "×", r"\div": "÷",
        r"\leq": "≤", r"\geq": "≥", r"\neq": "≠", r"\in": "∈",
    }
    result = value.casefold()
    for source, target in aliases.items():
        result = result.replace(source, target)
    return "".join(result.split()).replace("{", "(").replace("}", ")").replace("·", "×")


def evaluate(manifest: dict, gold: dict, predictions: list[dict]) -> dict:
    """Create a report with booleans/metrics only, never document content."""
    expected = {item["id"]: item for item in gold["formulas"]}
    actual = {item["id"]: item for item in predictions}
    ids = [item["id"] for item in manifest["regions"]]
    if set(ids) != set(expected):
        raise RuntimeError("formula input and Gold IDs do not match")
    records, exact, critical_exact, completed = [], 0, 0, 0
    critical_total = sum(bool(expected[item_id].get("critical", True)) for item_id in ids)
    for item_id in ids:
        prediction, reference = actual.get(item_id), expected[item_id]
        done = prediction is not None and prediction["status"] == "completed"
        matches = done and canonical(prediction["visible_notation"]) == canonical(reference["visible_notation"])
        completed += done
        exact += matches
        critical_exact += bool(reference.get("critical", True)) and matches
        records.append({"id": item_id, "status": prediction["status"] if prediction else "missing", "exact_notation": matches})
    total = len(ids)
    recall, accuracy = completed / total, exact / total
    critical_accuracy = critical_exact / max(critical_total, 1)
    passed = recall >= .95 and accuracy >= .98 and critical_accuracy == 1 and len(actual) == total
    return {
        "report_type": "formula-region-evaluation-v1", "contains_document_content": False,
        "candidate": CANDIDATE, "formula_regions": total, "completed_predictions": completed,
        "detection_recall": recall, "exact_notation_accuracy": accuracy,
        "critical_expression_accuracy": critical_accuracy,
        "decision": (
            "formula-gate-passed-teacher-review-still-required"
            if passed
            else "formula-gate-failed-experimental-review-allowed"
        ),
        "records": records,
    }


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "paddleocr[doc-parser]"], check=True)
    from paddleocr import FormulaRecognitionPipeline

    manifests = list(INPUT.rglob("formula-region-manifest.json"))
    golds = list(INPUT.rglob("formula-region-gold.json"))
    if len(manifests) != 1 or len(golds) != 1:
        raise RuntimeError("Private input must contain exactly one formula manifest and Gold file")
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    gold = json.loads(golds[0].read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "formula-region-benchmark-input-v1" or gold.get("schema_version") != "formula-region-gold-v1":
        raise RuntimeError("formula benchmark schema mismatch")
    # Kaggle's current Python image does not ship the Paddle static-runtime
    # dependency.  PaddleOCR documents its Transformers engine as a supported
    # alternative, and it can use the attached T4 without installing a second
    # framework runtime.
    pipeline = FormulaRecognitionPipeline(
        formula_recognition_model_name=CANDIDATE, engine="transformers", device="gpu"
    )
    raw, predictions = OUTPUT / "raw", []
    raw.mkdir()
    for position, region in enumerate(manifest["regions"], start=1):
        image = INPUT / region["asset_path"]
        if not image.is_file() or sha256(image) != region["asset_checksum"]:
            raise RuntimeError("private formula crop checksum mismatch")
        result_dir = raw / region["id"]
        try:
            output = list(pipeline.predict(str(image), use_layout_detection=False))
            if len(output) != 1:
                raise RuntimeError("unexpected formula result count")
            result_dir.mkdir()
            output[0].save_to_json(save_path=result_dir)
            notation = saved_result_notation(result_dir)
            predictions.append({"id": region["id"], "visible_notation": notation, "confidence": 0.0, "status": "completed" if notation else "no-formula"})
            print(f"[{position}/{len(manifest['regions'])}] completed {region['id']}")
        except Exception as error:  # noqa: BLE001 - keep remaining independent Gold regions measurable.
            predictions.append({"id": region["id"], "visible_notation": "", "confidence": 0.0, "status": "failed"})
            print(f"[{position}/{len(manifest['regions'])}] failed {region['id']} ({type(error).__name__})")
    (OUTPUT / "formula_predictions.json").write_text(json.dumps({"schema_version": "formula-region-predictions-v1", "candidate": CANDIDATE, "predictions": predictions}, ensure_ascii=False), encoding="utf-8")
    report = evaluate(manifest, gold, predictions)
    (OUTPUT / "formula_evaluation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "run_metadata.json").write_text(json.dumps({"candidate": CANDIDATE, "contains_document_content": False, "prediction_artifact_sha256": sha256(OUTPUT / "formula_predictions.json")}, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("formula_regions", "exact_notation_accuracy", "critical_expression_accuracy", "decision")}))


if __name__ == "__main__":
    main()
