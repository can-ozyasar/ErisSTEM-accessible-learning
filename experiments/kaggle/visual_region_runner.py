"""Kaggle T4: private MEB görsel bölgesinde PaddleOCR-VL tablo adayı deneyi.

Ham model işaretlemesi yalnız private artefact olarak kalır. Öğrenciye veya
tarayıcıya HTML verilmez; yalnız doğrulanmış JSON hücre taslağı üretilir.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import unicodedata
import zipfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

# Üç private Gold tablo bölgesi; P51/P46 smoke-test artefact'larıyla karışmaz.
INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-table-gold-regions-v1")
RUN_ID = "paddleocr-vl-1.6-transformers-table-gold-regions-v1"
OUTPUT = Path("/kaggle/working/eristem-private-visual-region-benchmark") / "runs" / RUN_ID
SCHEMA_VERSION = "visual-table-draft-v1"
MAX_MARKUP_CHARS = 200_000
NATIVE_EVIDENCE_FILENAME = "native-table-evidence-v1.json"
HIGH_SOURCE_AGREEMENT_F1 = 0.98


class TableMarkupError(ValueError):
    """Model işaretlemesi tablo şemasına güvenle dönüştürülemediğinde yükselir."""


class TableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, str]]] = []
        self.current_row: list[tuple[str, str]] | None = None
        self.current_cell: list[str] | None = None
        self.current_role: str | None = None
        self.table_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.table_depth += 1
        elif tag == "tr" and self.table_depth == 1:
            if self.current_row is not None:
                raise TableMarkupError("nested_row")
            self.current_row = []
        elif tag in {"td", "th"} and self.current_row is not None and self.current_cell is None:
            self.current_cell = []
            self.current_role = "header" if tag == "th" else "data"

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.current_cell is not None and self.current_row is not None:
            text = " ".join("".join(self.current_cell).split())
            self.current_row.append((self.current_role or "unknown", text))
            self.current_cell, self.current_role = None, None
        elif tag == "tr" and self.current_row is not None:
            if self.current_cell is not None:
                raise TableMarkupError("unclosed_cell")
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = None
        elif tag == "table" and self.table_depth:
            self.table_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.current_cell is not None:
            self.current_cell.append(data)

    def close(self) -> None:
        super().close()
        if self.table_depth or self.current_row is not None or self.current_cell is not None:
            raise TableMarkupError("unclosed_markup")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_manifest() -> tuple[Path, dict, Path]:
    manifests = list(INPUT.rglob("visual-regions.json"))
    roots = [INPUT]
    if not manifests and list(INPUT.rglob("*.zip")):
        unpacked = OUTPUT / "input"
        with zipfile.ZipFile(next(INPUT.rglob("*.zip"))) as source:
            source.extractall(unpacked)
        roots, manifests = [unpacked], list(unpacked.rglob("visual-regions.json"))
    if len(manifests) != 1:
        raise RuntimeError("Private input içinde tam bir visual-regions.json bulunmalı")
    manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("assets"):
        raise RuntimeError("Görsel bölge manifestinde asset bulunamadı")
    return manifest_path, manifest, roots[0]


def asset_path(manifest_path: Path, relative_path: str) -> Path:
    package_root = manifest_path.parent.resolve()
    declared = Path(relative_path)
    if declared.is_absolute() or ".." in declared.parts:
        raise RuntimeError("Manifest asset yolu izinli paketin dışında")
    direct = (package_root / declared).resolve()
    if direct.is_relative_to(package_root) and direct.is_file():
        return direct
    # v1 paketi, manifestte yalnız dosya adı taşıyıp asset'i alt klasöre koydu.
    # Fallback yalnız aynı paket kökündeki benzersiz dosya adına izin verir.
    matches = [
        candidate.resolve()
        for candidate in package_root.rglob(declared.name)
        if candidate.resolve().is_relative_to(package_root) and candidate.is_file()
    ]
    if len(matches) != 1:
        raise RuntimeError("Manifest asset yolu izinli paketin dışında veya eksik")
    return matches[0]


def iter_nodes(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_nodes(child)


def table_markup(result_dir: Path) -> list[str]:
    markup = []
    for path in result_dir.rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for node in iter_nodes(payload):
            label = str(node.get("block_label", node.get("label", ""))).lower()
            content = node.get("block_content")
            if label == "table" and isinstance(content, str) and "<table" in content.lower():
                markup.append(content)
    return list(dict.fromkeys(markup))


def structural_diagnostics(result_dir: Path) -> dict[str, object]:
    """Return content-free model-result diagnostics for a blocked region."""
    labels: Counter[str] = Counter()
    json_files = unreadable_json_files = table_markup_count = 0
    for path in result_dir.rglob("*.json"):
        json_files += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            unreadable_json_files += 1
            continue
        for node in iter_nodes(payload):
            label = str(node.get("block_label", node.get("label", ""))).lower()
            if label:
                labels[label] += 1
            content = node.get("block_content")
            if label == "table" and isinstance(content, str) and "<table" in content.lower():
                table_markup_count += 1
    return {
        "result_json_files": json_files,
        "unreadable_json_files": unreadable_json_files,
        "labels": dict(sorted(labels.items())),
        "table_markup_count": table_markup_count,
    }


def safe_error_code(error: Exception) -> str:
    """Keep model content out of logs while retaining actionable known failure codes."""
    if isinstance(error, TableMarkupError):
        return str(error)
    if isinstance(error, RuntimeError) and str(error).startswith("expected_one_table_markup_got_"):
        return str(error)
    return type(error).__name__


def normalized_tokens(value: str) -> list[str]:
    return [
        token
        for token in " ".join(unicodedata.normalize("NFKC", value).casefold().split()).split()
        if token
    ]


def native_source_agreement(drafts: list[dict], evidence_path: Path) -> dict:
    """Produce a content-free agreement proxy; this is never a Gold accuracy score."""
    try:
        document = json.loads(evidence_path.read_text(encoding="utf-8"))
        items = document["evidence"]
        if document.get("schema_version") != "native-table-evidence-v1" or not isinstance(items, list):
            raise ValueError("invalid_evidence_schema")
        evidence = {item["region_id"]: item for item in items}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {
            "report_type": "native-table-agreement-proxy-v1",
            "contains_document_content": False,
            "not_a_gold_accuracy_score": True,
            "status": "blocked-invalid-native-evidence",
            "records": [],
        }
    drafts_by_id = {draft.get("source", {}).get("region_id"): draft for draft in drafts}
    records = []
    for region_id, item in evidence.items():
        draft = drafts_by_id.get(region_id)
        if not isinstance(draft, dict):
            records.append({"region_id": region_id, "decision": "missing-draft"})
            continue
        source, expected_source = draft.get("source"), item.get("source")
        source_matches = (
            isinstance(source, dict)
            and isinstance(expected_source, dict)
            and source.get("page") == expected_source.get("page")
            and source.get("source_checksum") == expected_source.get("source_checksum")
            and list(source.get("bbox", [])) == list(expected_source.get("bbox", []))
        )
        if not source_matches:
            records.append({"region_id": region_id, "source_matches": False, "decision": "blocked-source-mismatch"})
            continue
        expected = item.get("tokens")
        actual = [
            token
            for cell in draft.get("cells", [])
            if isinstance(cell, dict) and isinstance(cell.get("text"), str)
            for token in normalized_tokens(cell["text"])
        ]
        if not isinstance(expected, list) or not all(isinstance(token, str) for token in expected):
            records.append({"region_id": region_id, "source_matches": True, "decision": "blocked-invalid-native-evidence"})
            continue
        overlap = sum((Counter(expected) & Counter(actual)).values())
        precision = overlap / len(actual) if actual else 0.0
        recall = overlap / len(expected) if expected else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        records.append(
            {
                "region_id": region_id,
                "source_matches": True,
                "token_precision": precision,
                "token_recall": recall,
                "token_f1": f1,
                "decision": (
                    "high-source-agreement-proxy-needs-gold"
                    if f1 >= HIGH_SOURCE_AGREEMENT_F1
                    else "low-source-agreement-needs-review"
                ),
            }
        )
    return {
        "report_type": "native-table-agreement-proxy-v1",
        "contains_document_content": False,
        "not_a_gold_accuracy_score": True,
        "status": "completed",
        "records": records,
    }


def adapt_table(markup: str, asset: dict) -> dict:
    if not markup or len(markup) > MAX_MARKUP_CHARS:
        raise TableMarkupError("invalid_markup_length")
    parser = TableTextParser()
    parser.feed(markup)
    parser.close()
    if not parser.rows:
        raise TableMarkupError("no_table_cells")
    source = asset["source"]
    required_source_keys = {"page", "bbox", "source_checksum"}
    if not required_source_keys <= source.keys() or len(source["bbox"]) != 4:
        raise TableMarkupError("invalid_source_manifest")
    cells = [
        {
            "row": row_index,
            "column": column_index,
            "role": role,
            "text": text,
            # PaddleOCR-VL bu çıktıda hücre-güveni sağlamaz. Uydurmak yerine sıfır verilir.
            "confidence": 0.0,
        }
        for row_index, row in enumerate(parser.rows, start=1)
        for column_index, (role, text) in enumerate(row, start=1)
    ]
    coordinates = [(cell["row"], cell["column"]) for cell in cells]
    if len(coordinates) != len(set(coordinates)) or not cells:
        raise TableMarkupError("invalid_cell_coordinates")
    return {
        "schema_version": SCHEMA_VERSION,
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


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    gpu = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=name,compute_cap,driver_version", "--format=csv,noheader"],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "paddleocr[doc-parser]"], check=True
    )
    from paddleocr import PaddleOCRVL

    manifest_path, manifest, _ = resolve_manifest()
    pipeline = PaddleOCRVL(engine="transformers")
    results_dir = OUTPUT / "results"
    records = []
    drafts = []
    for position, asset in enumerate(manifest["assets"], start=1):
        image = asset_path(manifest_path, asset["asset_path"])
        if sha256(image) != asset["asset_checksum"]:
            raise RuntimeError(f"Asset checksum uyuşmuyor: {asset['route_id']}")
        result_dir = results_dir / asset["route_id"]
        result_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{position}/{len(manifest['assets'])}] İşleniyor: {asset['route_id']}")
        try:
            output = list(pipeline.predict(str(image)))
            if len(output) != 1:
                raise RuntimeError(f"Beklenmeyen çıktı sayısı: {len(output)}")
            output[0].save_to_json(save_path=result_dir)
            output[0].save_to_markdown(save_path=result_dir)
            markup = table_markup(result_dir)
            if len(markup) != 1:
                raise TableMarkupError(f"expected_one_table_markup_got_{len(markup)}")
            drafts.append(adapt_table(markup[0], asset))
            records.append(
                {
                    "route_id": asset["route_id"],
                    "status": "validated_low_confidence_review_required",
                    "diagnostics": structural_diagnostics(result_dir),
                }
            )
            print(f"[{position}/{len(manifest['assets'])}] Şema doğrulandı: {asset['route_id']}")
        except (OSError, RuntimeError, TableMarkupError, json.JSONDecodeError) as error:
            records.append(
                {
                    "route_id": asset["route_id"],
                    "status": "blocked",
                    "error_code": safe_error_code(error),
                    "diagnostics": structural_diagnostics(result_dir),
                }
            )
            print(f"[{position}/{len(manifest['assets'])}] Engellendi: {asset['route_id']} ({type(error).__name__})")

    (OUTPUT / "table_drafts.json").write_text(json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "region_records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_path = manifest_path.parent / NATIVE_EVIDENCE_FILENAME
    agreement = (
        native_source_agreement(drafts, evidence_path)
        if evidence_path.is_file()
        else {
            "report_type": "native-table-agreement-proxy-v1",
            "contains_document_content": False,
            "not_a_gold_accuracy_score": True,
            "status": "not-provided",
            "records": [],
        }
    )
    (OUTPUT / "native_agreement_report.json").write_text(
        json.dumps(agreement, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUTPUT / "run_metadata.json").write_text(
        json.dumps(
            {
                "candidate": "paddleocr-vl",
                "engine": "transformers",
                "gpu": gpu,
                "paddleocr_version": importlib.metadata.version("paddleocr"),
                "input_private": True,
                "schema_version": SCHEMA_VERSION,
                "publication": "blocked_pending_teacher_review",
                "native_agreement_proxy_status": agreement["status"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    shutil.rmtree(OUTPUT / "input", ignore_errors=True)
    completed = sum(record["status"].startswith("validated") for record in records)
    print(f"Bitti: {completed}/{len(records)} şema taslağı doğrulandı; yayın kapalı.")


if __name__ == "__main__":
    main()
