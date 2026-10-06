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
import zipfile
from html.parser import HTMLParser
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-visual-regions-p51-v1")
OUTPUT = Path("/kaggle/working/eristem-private-visual-region-benchmark")
SCHEMA_VERSION = "visual-table-draft-v1"
MAX_MARKUP_CHARS = 200_000


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
    path = (manifest_path.parent / relative_path).resolve()
    if not path.is_relative_to(manifest_path.parent.resolve()) or not path.is_file():
        raise RuntimeError("Manifest asset yolu izinli paketin dışında veya eksik")
    return path


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
            records.append({"route_id": asset["route_id"], "status": "validated_low_confidence_review_required"})
            print(f"[{position}/{len(manifest['assets'])}] Şema doğrulandı: {asset['route_id']}")
        except (OSError, RuntimeError, TableMarkupError, json.JSONDecodeError) as error:
            records.append(
                {"route_id": asset["route_id"], "status": "blocked", "error_type": type(error).__name__}
            )
            print(f"[{position}/{len(manifest['assets'])}] Engellendi: {asset['route_id']} ({type(error).__name__})")

    (OUTPUT / "table_drafts.json").write_text(json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "region_records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
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
