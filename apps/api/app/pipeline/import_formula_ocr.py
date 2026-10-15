"""Import schema-checked whole-expression OCR proposals into teacher review.

This is deliberately a draft-only bridge.  A model result is converted to
normal visible notation, MathML and Turkish speech, but it never approves or
publishes a formula.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ..job_store import DocumentStore, make_session_factory
from .latex_ocr_adapter import LatexOcrError, latex_ocr_candidate


def pending_step_for_ocr_output(value: str) -> tuple[str, str]:
    """Route non-formula structures to their own review lane, never speech."""
    commands = set(re.findall(r"\\[A-Za-z]+", value))
    if {r"\begin", r"\end"} & commands:
        return "math-table-ocr-pending", "Tablo yapısı içeren matematik alanı; hücre tabanlı denetim gerekli."
    if {r"\angle", r"\circ", r"\dot", r"\underline", r"\overline"} & commands:
        return "math-geometry-ocr-pending", "Geometrik gösterim veya ölçü bağlamı; şekil ilişkisi denetimi gerekli."
    return "math-ocr-review-required", "Görsel OCR çıktısı desteklenen güvenli matematik dilinin dışında; uzman denetimi gerekli."


def load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid_json:{path.name}") from error
    if not isinstance(payload, dict):
        raise TypeError(f"invalid_json_object:{path.name}")
    return payload


def apply_formula_predictions(document: dict, manifest: dict, predictions: dict, bindings: dict) -> tuple[dict, int]:
    """Return a revised draft with only source-bound formula proposals applied."""
    if manifest.get("schema_version") != "formula-region-benchmark-input-v1":
        raise ValueError("invalid_formula_manifest")
    if predictions.get("schema_version") != "formula-region-predictions-v1":
        raise ValueError("invalid_formula_predictions")
    if bindings.get("schema_version") != "formula-ocr-bindings-v1" or bindings.get("document_id") != document.get("id"):
        raise ValueError("invalid_formula_bindings")
    regions = {item.get("id"): item for item in manifest.get("regions", []) if isinstance(item, dict)}
    candidates = {item.get("id"): item for item in predictions.get("predictions", []) if isinstance(item, dict)}
    if not regions or set(regions) != set(candidates):
        raise ValueError("formula_prediction_regions_mismatch")
    blocks = {block.get("id"): block for block in document.get("blocks", []) if isinstance(block, dict)}
    remove_ids: set[str] = set()
    applied = 0
    for binding in bindings.get("bindings", []):
        if not isinstance(binding, dict):
            raise TypeError("invalid_formula_binding")
        region_id, block_ids = binding.get("region_id"), binding.get("block_ids")
        if region_id not in regions or not isinstance(block_ids, list) or not block_ids or not all(isinstance(item, str) for item in block_ids):
            raise ValueError("invalid_formula_binding")
        if block_ids[0] not in blocks or blocks[block_ids[0]].get("kind") not in {"formula-display", "paragraph"}:
            raise ValueError("formula_binding_target_missing")
        # A previous successful import has already collapsed secondary broken
        # fragments.  Re-importing a newer proposal must remain idempotent.
        if any(block_id in blocks and blocks[block_id].get("kind") not in {"formula-display", "paragraph"} for block_id in block_ids[1:]):
            raise ValueError("formula_binding_target_missing")
        region, candidate = regions[region_id], candidates[region_id]
        if candidate.get("status") != "completed" or not isinstance(candidate.get("visible_notation"), str):
            continue
        try:
            visible, mathml, spoken = latex_ocr_candidate(candidate["visible_notation"])
        except LatexOcrError:
            step, reason = pending_step_for_ocr_output(candidate["visible_notation"])
            target = blocks[block_ids[0]]
            target.update(
                kind="formula-display", text=None, latex=None, mathml=None, spoken_text=None,
                validation={"schema_passed": True, "render_score": 0.0, "source_agreement": 0.0, "confidence": 0.0, "reasons": [reason]},
            )
            target["source"] = {**target["source"], "extraction_step": step}
            continue
        target = blocks[block_ids[0]]
        target.update(
            kind="formula-display",
            text=visible,
            latex=candidate["visible_notation"],
            mathml=mathml,
            spoken_text=spoken,
            status="review_required",
            revision=int(target.get("revision", 1)) + 1,
            validation={
                "schema_passed": True, "render_score": 1.0, "source_agreement": 0.0,
                "confidence": 0.0,
                "reasons": ["Bütün ifade görsel OCR önerisi; öğretmen kaynakla karşılaştırmalıdır."],
            },
        )
        target["source"] = {
            **target["source"], "page": region["page"], "bbox": region["bbox"],
            "extraction_step": f"formula-ocr:{predictions['candidate']}",
        }
        remove_ids.update(block_id for block_id in block_ids[1:] if block_id in blocks)
        applied += 1
    document["blocks"] = [block for block in document["blocks"] if block.get("id") not in remove_ids]
    return document, applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Import private formula OCR proposals into draft review")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--document", type=Path)
    target.add_argument("--document-id")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.document:
        document = load_json(args.document)
    else:
        store = DocumentStore(make_session_factory())
        document = store.get(args.document_id)
        if document is None:
            raise ValueError("document_not_found")
    document, applied = apply_formula_predictions(document, load_json(args.manifest), load_json(args.predictions), load_json(args.bindings))
    if args.output:
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.document_id:
        store.save_draft(document)
        store.add_audit(args.document_id, "admin", "formula_ocr_proposals_imported", None, f"{applied} whole-expression OCR proposals")
    print(json.dumps({"applied": applied}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
