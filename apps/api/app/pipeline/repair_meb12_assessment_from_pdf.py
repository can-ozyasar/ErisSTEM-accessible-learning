"""Repair incomplete MEB assessment OCR from the source PDF text layer.

The assessment candidate extractor can preserve choices while losing a stem
when a page has a multi-column layout.  This utility reconstructs only the
question block from the exact source PDF page, keeps the original geometry and
target-section metadata, and fails closed when an A--E sequence is incomplete.
It never reads answer keys or worked solutions and never marks a source as
approved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

QUESTION = re.compile(r"(?m)^\s*(\d{1,2})\.\s+")
# A few printed pages lose the closing parenthesis on a label (for example
# ``D I ve III``).  Requiring whitespace after the bare label keeps ordinary
# words such as ``Aşağıdaki`` and ``Devlet`` out of the option stream.
CHOICE = re.compile(r"(?<![A-Za-zÇĞİÖŞÜçğıöşü])([A-E])(?:\)|(?=\s))\s+")
TRAILING = re.compile(r"\s+\d+\s*$")


def _normalise(text: str) -> str:
    return " ".join(text.replace("\u00ad", "").split()).strip()


def _page_text(pdf: Path, page: int) -> str:
    result = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ValueError(f"PDF sayfa metni okunamadı: {page}")
    return result.stdout


def parse_page(text: str) -> dict[int, dict]:
    starts = list(QUESTION.finditer(text))
    parsed: dict[int, dict] = {}
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[start.start() : end]
        number = int(start.group(1))
        choices = list(CHOICE.finditer(block))
        if [item.group(1) for item in choices] != list("ABCDE"):
            continue
        stem = _normalise(block[start.end() - start.start() : choices[0].start()])
        stem = TRAILING.sub("", stem)
        options = []
        for choice_index, choice in enumerate(choices):
            option_end = choices[choice_index + 1].start() if choice_index + 1 < len(choices) else len(block)
            option = _normalise(block[choice.end() : option_end])
            option = TRAILING.sub("", option)
            if not option:
                break
            options.append({"label": choice.group(1), "text": option})
        if stem and len(options) == 5:
            parsed[number] = {"number": number, "stem": stem, "choices": options}
    return parsed


def _question(row: dict, parsed: dict) -> dict:
    old = row["question"]
    source = old.get("source", {})
    parts = [{
        "id": f'{old["id"]}-part-1',
        "kind": "stem",
        "text": parsed["stem"],
        "source": source,
        "blanks": [],
    }]
    return {
        "id": old["id"],
        "number": parsed["number"],
        "question_type": "multiple_choice",
        "source": source,
        "parts": parts,
        "choices": [
            {"label": item["label"], "text": item["text"], "source": source}
            for item in parsed["choices"]
        ],
        "visuals": [],
        "status": "draft",
    }


def build(original: dict, pdf: Path, pages: set[int] | None = None) -> tuple[dict, dict]:
    if original.get("schema") != "ayt-target-question-candidates-v1":
        raise ValueError("MEB ölçme adayı şeması geçersiz")
    checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
    expected = original.get("source_checksum")
    if expected and expected != checksum:
        raise ValueError("PDF checksum aday havuzuyla eşleşmiyor")
    by_page: dict[int, dict[int, dict]] = {}
    for page in sorted({row["page"] for row in original.get("rows", []) if pages is None or row["page"] in pages}):
        by_page[page] = parse_page(_page_text(pdf, page))
    rows, unresolved = [], []
    for row in original.get("rows", []):
        if pages is not None and row["page"] not in pages:
            continue
        parsed = by_page.get(row["page"], {}).get(row["question"]["number"])
        if parsed is None:
            unresolved.append(row["candidate_id"])
            continue
        rows.append({**row, "question": _question(row, parsed),
                     "transcription_status": "private_pdf_text_repaired",
                     "answer_key_accessed": False, "worked_explanation_accessed": False})
    output = {
        "schema": original["schema"],
        "source_checksum": checksum,
        "rows": rows,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Private PDF-text repair only; no source approval or runtime eligibility.",
    }
    report = {
        "schema": "meb12-assessment-pdf-repair-report-v1",
        "source_checksum": checksum,
        "requested_pages": sorted(pages) if pages is not None else sorted(by_page),
        "repaired_count": len(rows),
        "unresolved_count": len(unresolved),
        "unresolved_candidate_ids": unresolved,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
    }
    return output, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--pages", help="Virgülle sayfa listesi; verilmezse tüm aday sayfaları")
    args = parser.parse_args()
    pages = {int(item) for item in args.pages.split(",")} if args.pages else None
    original = json.loads(args.original.read_text(encoding="utf-8"))
    content, report = build(original, args.pdf, pages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
