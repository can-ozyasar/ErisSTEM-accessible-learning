"""Private native-text evidence for visual-table benchmark triage.

This is deliberately an independent source-agreement proxy, not Gold truth.
It reduces the cells a reviewer needs to inspect but cannot approve a model or
publish material by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

from .pdf_text_layer import PdfSafetyError, SourceCoordinate, _read_and_validate
from .visual_table_benchmark import _candidate_from_payload

EVIDENCE_SCHEMA_VERSION = "native-table-evidence-v1"
HIGH_AGREEMENT_F1 = 0.98


@dataclass(frozen=True)
class NativeTableEvidence:
    region_id: str
    source: SourceCoordinate
    tokens: list[str]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _asset_source(asset: dict) -> SourceCoordinate:
    source = asset.get("source")
    if not isinstance(source, dict):
        raise PdfSafetyError("Görsel bölge kaynak bilgisi eksik")
    bbox = source.get("bbox")
    if (
        not isinstance(asset.get("route_id"), str)
        or not isinstance(source.get("page"), int)
        or not isinstance(bbox, list)
        or len(bbox) != 4
        or not all(isinstance(value, int | float) for value in bbox)
        or not isinstance(source.get("source_checksum"), str)
    ):
        raise PdfSafetyError("Görsel bölge kaynak şeması geçersiz")
    return SourceCoordinate(
        page=source["page"],
        bbox=tuple(float(value) for value in bbox),
        source_checksum=source["source_checksum"],
        extraction_step="native-table-evidence",
    )


def _tokenize(value: str) -> list[str]:
    """Normalise benign notation differences without discarding maths operators."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    for latex, symbol in (
        (r"\notin", "∉"),
        (r"\subseteq", "⊆"),
        (r"\subset", "⊂"),
        (r"\emptyset", "∅"),
        (r"\varnothing", "∅"),
        (r"\setminus", "∖"),
        (r"\cup", "∪"),
        (r"\cap", "∩"),
        (r"\in", "∈"),
    ):
        normalized = normalized.replace(latex, symbol)
    normalized = normalized.translate(str.maketrans({"∖": "\\", "′": " prime ", "’": " prime ", "'": " prime "}))
    return re.findall(r"[\w]+|[∪∩∅∈∉⊆⊂\\=+\-/]", normalized, flags=re.UNICODE)


def _words_in_region(page: pymupdf.Page, bbox: tuple[float, float, float, float]) -> list[str]:
    region = pymupdf.Rect(bbox)
    words = page.get_text("words", clip=region, sort=True)
    output = []
    for x0, y0, x1, y1, text, *_ in words:
        centre = pymupdf.Point((x0 + x1) / 2, (y0 + y1) / 2)
        if region.contains(centre):
            output.extend(_tokenize(text))
    return output


def extract_native_table_evidence(path: Path, source_root: Path, regions_manifest: Path) -> dict:
    """Extract private native text tokens within checksum-bound table regions."""
    _, content = _read_and_validate(path, source_root)
    checksum = _sha256(content)
    payload = json.loads(regions_manifest.read_text(encoding="utf-8"))
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list) or not assets:
        raise PdfSafetyError("Görsel bölge manifestinde asset bulunamadı")
    evidence = []
    with pymupdf.open(stream=content, filetype="pdf") as document:
        for asset in assets:
            if not isinstance(asset, dict):
                raise PdfSafetyError("Görsel bölge asset şeması geçersiz")
            source = _asset_source(asset)
            if source.source_checksum != checksum or source.page < 1 or source.page > document.page_count:
                raise PdfSafetyError("Görsel bölge kaynağı PDF ile uyuşmuyor")
            evidence.append(
                NativeTableEvidence(
                    region_id=asset["route_id"],
                    source=source,
                    tokens=_words_in_region(document[source.page - 1], source.bbox),
                )
            )
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "contains_document_content": True,
        "evidence": [asdict(item) for item in evidence],
    }


def _source_matches(candidate: dict, evidence: dict) -> bool:
    source = candidate.get("source")
    expected = evidence.get("source")
    if not isinstance(source, dict) or not isinstance(expected, dict):
        return False
    return (
        source.get("page") == expected.get("page")
        and source.get("source_checksum") == expected.get("source_checksum")
        and list(source.get("bbox", [])) == list(expected.get("bbox", []))
    )


def _multiset_f1(expected: list[str], actual: list[str]) -> tuple[float, float, float]:
    expected_counts, actual_counts = Counter(expected), Counter(actual)
    overlap = sum((expected_counts & actual_counts).values())
    precision = overlap / len(actual) if actual else 0.0
    recall = overlap / len(expected) if expected else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def score_native_table_agreement(drafts: list[dict], evidence_document: dict) -> dict:
    """Return content-free model/source agreement signals, never a Gold decision."""
    if evidence_document.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise ValueError("native evidence schema version is invalid")
    evidence_by_id = {item["region_id"]: item for item in evidence_document.get("evidence", [])}
    records = []
    for payload in drafts:
        try:
            candidate = _candidate_from_payload(payload)
        except (TypeError, ValueError):
            continue
        evidence = evidence_by_id.get(candidate.source.region_id)
        if not evidence or not _source_matches(candidate.model_dump(), evidence):
            records.append({"region_id": candidate.source.region_id, "source_matches": False, "decision": "blocked-source-mismatch"})
            continue
        actual = [token for cell in candidate.cells for token in _tokenize(cell.text)]
        expected = [token for value in evidence["tokens"] for token in _tokenize(value)]
        precision, recall, f1 = _multiset_f1(expected, actual)
        records.append(
            {
                "region_id": candidate.source.region_id,
                "source_matches": True,
                "token_precision": precision,
                "token_recall": recall,
                "token_f1": f1,
                "decision": (
                    "high-source-agreement-proxy-needs-gold"
                    if f1 >= HIGH_AGREEMENT_F1
                    else "low-source-agreement-needs-review"
                ),
            }
        )
    return {
        "report_type": "native-table-agreement-proxy-v1",
        "contains_document_content": False,
        "not_a_gold_accuracy_score": True,
        "tokenization": "mathematical-canonical-v2",
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Private native visual-table evidence")
    subcommands = parser.add_subparsers(dest="command", required=True)
    extract = subcommands.add_parser("extract")
    extract.add_argument("--input", type=Path, required=True)
    extract.add_argument("--source-root", type=Path, default=Path("data/meb"))
    extract.add_argument("--regions", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)
    score = subcommands.add_parser("score")
    score.add_argument("--drafts", type=Path, required=True)
    score.add_argument("--evidence", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "extract":
        result = extract_native_table_evidence(args.input, args.source_root, args.regions)
    else:
        drafts = json.loads(args.drafts.read_text(encoding="utf-8"))
        result = score_native_table_agreement(drafts, json.loads(args.evidence.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
