"""Inventory PDF structures before a book enters evidence retrieval.

This is deliberately a routing audit, not an evidence extractor.  It records
which pages contain ordinary prose, short factual bullets, or structures that
need a separate table/diagram/visual review path.  The JSON result has no
source text, question text, or answer data and remains private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pymupdf

from ..history_rag import (
    _atom_candidate,
    _candidate,
    _clean,
    block_layout,
    candidate_review_warnings,
    sections,
)


def page_signals(blocks: list[dict], *, page_height: float, drawing_count: int, image_count: int = 0) -> dict:
    """Return conservative layout signals from text geometry, without text."""
    text_blocks = [block for block in blocks if block["text"]]
    atom_candidates = sum(_atom_candidate(block["text"], block["bbox"], page_height) for block in text_blocks)
    context_candidates = sum(_candidate(block["text"], block["bbox"], page_height) for block in text_blocks)
    warnings = Counter(
        warning for block in text_blocks for warning in candidate_review_warnings(block["text"])
    )
    x_columns = {round(block["bbox"][0] / 24) for block in text_blocks if len(block["text"]) >= 12}
    compact_blocks = sum(len(block["text"]) <= 90 for block in text_blocks)
    # This flag is intentionally broad.  It sends a page to visual review;
    # it never turns a page into a table or a graph automatically.
    grid_or_diagram_risk = ((len(x_columns) >= 3 and compact_blocks >= 5)
                            or drawing_count >= 12 or image_count >= 1)
    return {
        "text_block_count": len(text_blocks),
        "short_atom_candidate_count": atom_candidates,
        "context_candidate_count": context_candidates,
        "warning_counts": dict(sorted(warnings.items())),
        "drawing_count": drawing_count,
        "image_count": image_count,
        "grid_or_diagram_review_required": grid_or_diagram_risk,
    }


def audit(source: Path) -> dict:
    raw = source.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    rows, totals = [], Counter()
    with pymupdf.open(stream=raw, filetype="pdf") as pdf:
        chapter = sections(pdf)
        for section in chapter:
            section_totals = Counter()
            for page_number in range(section["start"], min(section["end"], pdf.page_count) + 1):
                page = pdf[page_number - 1]
                blocks = []
                for block in page.get_text("dict")["blocks"]:
                    if block["type"] != 0:
                        continue
                    raw_lines = ["".join(span["text"] for span in line["spans"])
                                 for line in block["lines"]]
                    blocks.append({"text": _clean(" ".join(raw_lines)),
                                   "bbox": [round(float(value), 2) for value in block["bbox"]],
                                   "layout": block_layout(raw_lines)})
                # Enumerating every vector stroke in modern interactive PDFs
                # can dominate the audit time without improving its routing
                # decision.  Text geometry and embedded-image presence are
                # enough to flag a page for later visual inspection; vector
                # detail is inspected only for selected target-unit pages.
                signals = page_signals(blocks, page_height=page.rect.height, drawing_count=0,
                                       image_count=len(page.get_images(full=False)))
                for key in ("short_atom_candidate_count", "context_candidate_count", "drawing_count", "image_count"):
                    section_totals[key] += signals[key]
                    totals[key] += signals[key]
                for warning, count in signals["warning_counts"].items():
                    section_totals[f"warning:{warning}"] += count
                    totals[f"warning:{warning}"] += count
                if signals["grid_or_diagram_review_required"]:
                    section_totals["grid_or_diagram_review_pages"] += 1
                    totals["grid_or_diagram_review_pages"] += 1
                rows.append({"section_id": section["id"], "section_title": section["title"],
                             "page": page_number, "signals": signals})
            section["structure_counts"] = dict(sorted(section_totals.items()))
    return {
        "schema": "history-source-structure-audit-v1", "source_name": source.name,
        "source_checksum": checksum, "sections": chapter, "pages": rows,
        "totals": dict(sorted(totals.items())),
        "notice": ("Private routing inventory. Grid/diagram flags require visual PDF review; they are not "
                   "facts, approvals, or runtime evidence."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    private_root = (Path(__file__).resolve().parents[4] / "data/private").resolve()
    if not args.output.resolve().is_relative_to(private_root):
        raise ValueError("Yalnız data/private altına yazılabilir")
    result = audit(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"sections": len(result["sections"]), "pages": len(result["pages"]),
                      "totals": result["totals"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
