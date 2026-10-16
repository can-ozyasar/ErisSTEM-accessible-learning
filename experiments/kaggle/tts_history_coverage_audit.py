"""Inventory TTS-risk text patterns across the local MEB history PDF.

This is a source-bound sampling aid, not OCR correction, a quality score, or
permission to publish the book. Short excerpts remain under data/private.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/meb/tarih-9sinif-ders-kitabi_20261006.pdf"
OUTPUT = ROOT / "data/private/tts_history_lesson_coverage_v2.json"
LESSON_START_PAGE = 10  # Physical PDF page; pages 1–9 are covers/front matter.
MAX_EXAMPLES = 12
PATTERNS = {
    "source_letter": re.compile(r"\b(?i:Kaynak)\s+(?P<letter>[A-ZÇĞİÖŞÜ])(?=\b|['’])"),
    "apostrophe_suffix": re.compile(r"\b[^\W\d_]{1,30}['’][^\W\d_]{1,15}\b", re.UNICODE),
    "initialism": re.compile(r"\b[A-ZÇĞİÖŞÜ]{2,8}\b"),
    "year_or_year_range": re.compile(r"\b\d{3,4}(?:\s*[-–]\s*\d{2,4})?\b"),
    "roman_century": re.compile(r"\b[IVXLCDM]{2,6}\.\s*yüzyıl\b", re.I),
    "abbreviation": re.compile(r"(?<!\w)(?:MÖ|MS|M\.Ö\.|M\.S\.|bkz\.|s\.|yy\.)(?!\w)", re.I),
    "accented_spelling": re.compile(r"[ÀÁÂÄÉÈÊËÍÎÏÑÓÔÚÛàáâäéèêëíîïñóôúûÿ]"),
    "dense_punctuation": re.compile(r"[;…]|\.{3}|[()]"),
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def excerpt(line: str, position: int) -> str:
    start = max(0, position - 65)
    end = min(len(line), position + 125)
    return ("…" if start else "") + line[start:end].strip() + ("…" if end < len(line) else "")


def audit(pdf_path: Path) -> dict:
    categories = {name: {"matches": 0, "pages": set(), "examples": [], "letters": Counter()} for name in PATTERNS}
    with pymupdf.open(pdf_path) as pdf:
        page_count = pdf.page_count
        for page_index in range(LESSON_START_PAGE - 1, page_count):
            page = pdf[page_index]
            for block in page.get_text("blocks"):
                x0, y0, x1, y1, content, *_ = block
                if y0 < 40 or y1 > page.rect.height - 48 or not isinstance(content, str):
                    continue  # exclude running header and page furniture
                for raw_line in content.splitlines():
                    line = re.sub(r"\s+", " ", raw_line.replace("\xad", "")).strip()
                    if not line:
                        continue
                    for name, pattern in PATTERNS.items():
                        matches = list(pattern.finditer(line))
                        if not matches:
                            continue
                        row = categories[name]
                        row["matches"] += len(matches)
                        row["pages"].add(page_index + 1)
                        if name == "source_letter":
                            row["letters"].update(match.group("letter") for match in matches)
                        if len(row["examples"]) < MAX_EXAMPLES and not any(
                            example["page"] == page_index + 1 for example in row["examples"]
                        ):
                            row["examples"].append({"page": page_index + 1,
                                                    "excerpt": excerpt(line, matches[0].start())})
    summary = {name: {"matches": row["matches"], "pages": len(row["pages"]),
                      "examples": row["examples"]} for name, row in categories.items()}
    summary["source_letter"]["letters"] = dict(sorted(categories["source_letter"]["letters"].items()))
    return {"schema_version": "tts-history-coverage-audit-v2",
            "source_sha256": digest(pdf_path), "page_count": page_count,
            "scanned_pages": [LESSON_START_PAGE, page_count],
            "categories": summary,
            "notice": "Regex source-text inventory only; examples require visual/source verification before TTS evaluation."}


def main() -> None:
    report = audit(SOURCE)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists() and json.loads(OUTPUT.read_text(encoding="utf-8")) != report:
        raise FileExistsError("Var olan private audit farklı; üzerine yazılmadı")
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"page_count": report["page_count"], "source_sha256": report["source_sha256"],
                      "categories": {key: {"matches": value["matches"], "pages": value["pages"]}
                                     for key, value in report["categories"].items()},
                      "private_report": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
