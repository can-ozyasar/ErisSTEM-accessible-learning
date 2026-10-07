"""Kaggle T4: private visual-table regions, Docling comparison candidate.

Raw Docling Markdown remains in the private run directory. It is parsed as
untrusted data into a strict JSON table draft; it is never rendered as HTML.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-table-gold-regions-v2")
RUN_ID = "docling-table-gold-regions-v2"
OUTPUT = Path("/kaggle/working/eristem-private-visual-region-benchmark") / "runs" / RUN_ID
MAX_MARKDOWN_CHARS = 200_000
NATIVE_EVIDENCE_FILENAME = "native-table-evidence-v1.json"
HIGH_SOURCE_AGREEMENT_F1 = 0.98


class TableMarkupError(ValueError):
    """Untrusted Markdown cannot be safely treated as exactly one simple table."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_manifest() -> tuple[Path, dict]:
    manifests = list(INPUT.rglob("visual-regions.json"))
    if not manifests and list(INPUT.rglob("*.zip")):
        unpacked = OUTPUT / "input"
        with zipfile.ZipFile(next(INPUT.rglob("*.zip"))) as source:
            source.extractall(unpacked)
        manifests = list(unpacked.rglob("visual-regions.json"))
    if len(manifests) != 1:
        raise RuntimeError("Private input içinde tam bir visual-regions.json bulunmalı")
    manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest.get("assets"), list) or not manifest["assets"]:
        raise RuntimeError("Görsel bölge manifestinde asset bulunamadı")
    return manifest_path, manifest


def asset_path(manifest_path: Path, relative_path: str) -> Path:
    package_root = manifest_path.parent.resolve()
    declared = Path(relative_path)
    if declared.is_absolute() or ".." in declared.parts:
        raise RuntimeError("Manifest asset yolu izinli paketin dışında")
    direct = (package_root / declared).resolve()
    if direct.is_relative_to(package_root) and direct.is_file():
        return direct
    matches = [
        candidate.resolve()
        for candidate in package_root.rglob(declared.name)
        if candidate.resolve().is_relative_to(package_root) and candidate.is_file()
    ]
    if len(matches) != 1:
        raise RuntimeError("Manifest asset yolu izinli paketin dışında veya eksik")
    return matches[0]


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _cells(line: str) -> list[str]:
    cells = [" ".join(cell.replace(r"\|", "|").split()) for cell in line.strip().strip("|").split("|")]
    if not cells or any(len(cell) > 4000 for cell in cells):
        raise TableMarkupError("invalid_table_cells")
    return cells


def markdown_table(markdown: str) -> list[list[tuple[str, str]]]:
    """Extract exactly one simple pipe-table from untrusted Markdown."""
    if not markdown or len(markdown) > MAX_MARKDOWN_CHARS:
        raise TableMarkupError("invalid_markdown_length")
    lines = markdown.splitlines()
    tables = []
    index = 0
    while index + 1 < len(lines):
        if not (_is_table_row(lines[index]) and _is_separator(lines[index + 1])):
            index += 1
            continue
        header = _cells(lines[index])
        rows = [[("header", cell) for cell in header]]
        index += 2
        while index < len(lines) and _is_table_row(lines[index]):
            cells = _cells(lines[index])
            if len(cells) != len(header):
                raise TableMarkupError("inconsistent_column_count")
            rows.append([("data", cell) for cell in cells])
            index += 1
        if len(rows) < 2:
            raise TableMarkupError("table_has_no_data_rows")
        tables.append(rows)
    if len(tables) != 1:
        raise TableMarkupError(f"expected_one_markdown_table_got_{len(tables)}")
    return tables[0]


def adapt_table(markdown: str, asset: dict) -> dict:
    rows = markdown_table(markdown)
    source = asset.get("source")
    if not isinstance(source, dict) or not {"page", "bbox", "source_checksum"} <= source.keys():
        raise TableMarkupError("invalid_source_manifest")
    cells = [
        {"row": row, "column": column, "role": role, "text": text, "confidence": 0.0}
        for row, values in enumerate(rows, start=1)
        for column, (role, text) in enumerate(values, start=1)
    ]
    return {
        "schema_version": "visual-table-draft-v1",
        "kind": "table",
        "source": {
            "region_id": asset["route_id"],
            "source_checksum": source["source_checksum"],
            "page": source["page"],
            "bbox": source["bbox"],
        },
        "cells": cells,
        "confidence": 0.0,
        "publication_status": "requires-schema-validation-and-teacher-review",
    }


def normalized_tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    for latex, symbol in (
        (r"\notin", "∉"), (r"\subseteq", "⊆"), (r"\subset", "⊂"), (r"\emptyset", "∅"),
        (r"\varnothing", "∅"), (r"\setminus", "∖"), (r"\cup", "∪"), (r"\cap", "∩"), (r"\in", "∈"),
    ):
        normalized = normalized.replace(latex, symbol)
    normalized = normalized.translate(str.maketrans({"∖": "\\", "′": " prime ", "’": " prime ", "'": " prime "}))
    return re.findall(r"[\w]+|[∪∩∅∈∉⊆⊂\\=+\-/]", normalized, flags=re.UNICODE)


def native_source_agreement(drafts: list[dict], evidence_path: Path) -> dict:
    """Content-free agreement proxy; it never provides a Gold or publishing decision."""
    try:
        document = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence = {item["region_id"]: item for item in document["evidence"]}
        if document.get("schema_version") != "native-table-evidence-v1":
            raise ValueError("invalid_evidence_schema")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {"status": "blocked-invalid-native-evidence", "records": []}
    drafts_by_id = {draft.get("source", {}).get("region_id"): draft for draft in drafts}
    records = []
    for region_id, item in evidence.items():
        draft = drafts_by_id.get(region_id)
        source, expected = (draft or {}).get("source"), item.get("source")
        source_matches = (
            isinstance(source, dict) and isinstance(expected, dict)
            and source.get("page") == expected.get("page")
            and source.get("source_checksum") == expected.get("source_checksum")
            and list(source.get("bbox", [])) == list(expected.get("bbox", []))
        )
        if not isinstance(draft, dict) or not source_matches:
            records.append({"region_id": region_id, "source_matches": False, "decision": "missing-or-mismatched-draft"})
            continue
        expected_tokens = [token for value in item["tokens"] for token in normalized_tokens(value)]
        actual_tokens = [
            token for cell in draft["cells"] for token in normalized_tokens(cell["text"])
        ]
        overlap = sum((Counter(expected_tokens) & Counter(actual_tokens)).values())
        precision = overlap / len(actual_tokens) if actual_tokens else 0.0
        recall = overlap / len(expected_tokens) if expected_tokens else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        records.append({
            "region_id": region_id, "source_matches": True, "token_precision": precision,
            "token_recall": recall, "token_f1": f1,
            "decision": "high-source-agreement-proxy-needs-gold" if f1 >= HIGH_SOURCE_AGREEMENT_F1 else "low-source-agreement-needs-review",
        })
    return {
        "report_type": "native-table-agreement-proxy-v1", "contains_document_content": False,
        "not_a_gold_accuracy_score": True, "tokenization": "mathematical-canonical-v2",
        "status": "completed", "records": records,
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "docling"], check=True)
    from docling.document_converter import DocumentConverter

    manifest_path, manifest = resolve_manifest()
    converter = DocumentConverter()
    drafts, records = [], []
    raw_dir = OUTPUT / "private-raw"
    for position, asset in enumerate(manifest["assets"], start=1):
        image = asset_path(manifest_path, asset["asset_path"])
        if sha256(image) != asset["asset_checksum"]:
            raise RuntimeError(f"Asset checksum uyuşmuyor: {asset['route_id']}")
        print(f"[{position}/{len(manifest['assets'])}] İşleniyor: {asset['route_id']}")
        try:
            result = converter.convert(str(image))
            markdown = result.document.export_to_markdown()
            asset_raw = raw_dir / f"{asset['route_id']}.md"
            asset_raw.parent.mkdir(parents=True, exist_ok=True)
            asset_raw.write_text(markdown, encoding="utf-8")
            drafts.append(adapt_table(markdown, asset))
            records.append({"route_id": asset["route_id"], "status": "validated_low_confidence_review_required"})
            print(f"[{position}/{len(manifest['assets'])}] Şema doğrulandı: {asset['route_id']}")
        except (OSError, RuntimeError, TableMarkupError) as error:
            records.append({"route_id": asset["route_id"], "status": "blocked", "error_type": type(error).__name__})
            print(f"[{position}/{len(manifest['assets'])}] Engellendi: {asset['route_id']} ({type(error).__name__})")
    (OUTPUT / "table_drafts.json").write_text(json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "region_records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    agreement = native_source_agreement(drafts, manifest_path.parent / NATIVE_EVIDENCE_FILENAME)
    (OUTPUT / "native_agreement_report.json").write_text(json.dumps(agreement, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "run_metadata.json").write_text(json.dumps({
        "candidate": "docling", "docling_version": importlib.metadata.version("docling"),
        "input_private": True, "publication": "blocked_pending_teacher_review",
        "native_agreement_proxy_status": agreement["status"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(OUTPUT / "input", ignore_errors=True)
    print(f"Bitti: {sum(item['status'].startswith('validated') for item in records)}/{len(records)} şema taslağı doğrulandı; yayın kapalı.")


if __name__ == "__main__":
    main()
