"""Re-score existing private visual-table drafts without re-running the VLM."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

INPUT = Path("/kaggle/input/datasets/muhammedcanozyasar/eristem-meb9-table-gold-regions-v2")
RUN = Path(
    "/kaggle/working/eristem-private-visual-region-benchmark/"
    "runs/paddleocr-vl-1.6-transformers-table-gold-regions-v2"
)
EVIDENCE_FILENAME = "native-table-evidence-v1.json"
OUTPUT_FILENAME = "native_agreement_report_math_v2.json"
HIGH_SOURCE_AGREEMENT_F1 = 0.98


def normalized_tokens(value: str) -> list[str]:
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


def source_matches(draft: dict, evidence: dict) -> bool:
    source, expected = draft.get("source"), evidence.get("source")
    return (
        isinstance(source, dict)
        and isinstance(expected, dict)
        and source.get("page") == expected.get("page")
        and source.get("source_checksum") == expected.get("source_checksum")
        and list(source.get("bbox", [])) == list(expected.get("bbox", []))
    )


def main() -> None:
    evidence_paths = list(INPUT.rglob(EVIDENCE_FILENAME))
    if len(evidence_paths) != 1:
        raise RuntimeError("Private input içinde tam bir native evidence dosyası bulunmalı")
    drafts = json.loads((RUN / "table_drafts.json").read_text(encoding="utf-8"))
    document = json.loads(evidence_paths[0].read_text(encoding="utf-8"))
    if document.get("schema_version") != "native-table-evidence-v1":
        raise RuntimeError("Native evidence şema sürümü geçersiz")
    drafts_by_region = {draft.get("source", {}).get("region_id"): draft for draft in drafts}
    records = []
    for evidence in document["evidence"]:
        region_id = evidence["region_id"]
        draft = drafts_by_region.get(region_id)
        if not isinstance(draft, dict):
            records.append({"region_id": region_id, "decision": "missing-draft"})
            continue
        if not source_matches(draft, evidence):
            records.append({"region_id": region_id, "source_matches": False, "decision": "blocked-source-mismatch"})
            continue
        expected = [token for value in evidence["tokens"] for token in normalized_tokens(value)]
        actual = [
            token
            for cell in draft.get("cells", [])
            if isinstance(cell, dict) and isinstance(cell.get("text"), str)
            for token in normalized_tokens(cell["text"])
        ]
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
    report = {
        "report_type": "native-table-agreement-proxy-v1",
        "contains_document_content": False,
        "not_a_gold_accuracy_score": True,
        "tokenization": "mathematical-canonical-v2",
        "status": "completed",
        "records": records,
    }
    output = RUN / OUTPUT_FILENAME
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
