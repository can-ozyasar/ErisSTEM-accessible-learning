"""Strict local OCR extraction from already classified OGM AYT test pages."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

SCHEMA = "ogm-ayt-ocr-question-candidates-v1"
START = re.compile(r"(?m)^\s*(\d{1,2})[.)]\s+")
# OCR can place two horizontally adjacent options on the same reconstructed
# line.  A label still needs its option punctuation and following whitespace;
# the full A--E sequence gate below prevents partial matches from entering.
CHOICE = re.compile(r"\b([A-E])[.)]\s+")
FORBIDDEN = re.compile(r"\b(?:cevap|çözüm)\b", re.IGNORECASE)


def _ocr_columns(image: Path) -> list[str]:
    # Automatic page layout keeps the two printed columns separate.  A
    # single-uniform-block mode interleaves their choices and must not feed the
    # parser below.
    result = subprocess.run(["tesseract", str(image), "stdout", "-l", "tur", "--psm", "3", "tsv"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ValueError(f"OCR başarısız: {image.name}")
    words = list(csv.DictReader(result.stdout.splitlines(), delimiter="\t"))
    page = next((row for row in words if row.get("level") == "1"), None)
    if not page or not page.get("width", "").isdigit():
        raise ValueError(f"OCR sayfa boyutu okunamadı: {image.name}")
    midpoint = int(page["width"]) / 2
    lines: dict[tuple[int, str, str, str], list[dict]] = {}
    for word in words:
        text, left = word.get("text", "").strip(), word.get("left", "")
        if not text or not left.isdigit():
            continue
        column = 0 if int(left) < midpoint else 1
        key = (column, word.get("block_num", ""), word.get("par_num", ""), word.get("line_num", ""))
        lines.setdefault(key, []).append(word)
    columns = [[], []]
    for (column, *_), values in lines.items():
        if not values[0].get("top", "").isdigit():
            continue
        columns[column].append((
            int(values[0]["top"]), int(values[0]["left"]),
            " ".join(item["text"] for item in sorted(values, key=lambda item: int(item["left"]))),
        ))
    return ["\n".join(item[2] for item in sorted(column)) for column in columns]


def extract_page(text: str) -> tuple[list[dict], Counter[str]]:
    starts = list(START.finditer(text))
    accepted, rejected = [], Counter()
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[start.start():end].strip()
        if FORBIDDEN.search(block):
            rejected["solution_or_answer_marker"] += 1
            continue
        choices = list(CHOICE.finditer(block))
        labels = [item.group(1) for item in choices]
        if labels != list("ABCDE"):
            rejected["incomplete_or_unordered_choices"] += 1
            continue
        stem = block[start.end() - start.start():choices[0].start()].strip()
        option_text = []
        for choice_index, choice in enumerate(choices):
            choice_end = choices[choice_index + 1].start() if choice_index + 1 < len(choices) else len(block)
            option = block[choice.end():choice_end].strip()
            if not option:
                rejected["empty_choice"] += 1
                break
            option_text.append({"label": choice.group(1), "text": option})
        else:
            if not stem:
                rejected["empty_stem"] += 1
                continue
            accepted.append({"source_number": int(start.group(1)), "stem": stem, "choices": option_text})
    return accepted, rejected


def build(classification: dict, image_root: Path, pages: list[int] | None = None) -> tuple[dict, dict]:
    if classification.get("schema") != "ogm-ayt-page-classification-v1":
        raise ValueError("Sayfa sınıflandırma şeması geçersiz")
    requested = set(pages or [])
    rows, content, rejected = [], [], Counter()
    for page in classification.get("pages", []):
        number = page["page"]
        if page.get("category") != "test_candidate" or (requested and number not in requested):
            continue
        image = image_root / "pages" / f"{number:03d}.jpg"
        if not image.is_file():
            rejected["image_not_cached"] += 1
            continue
        accepted = []
        for column_text in _ocr_columns(image):
            column_accepted, page_rejected = extract_page(column_text)
            accepted.extend(column_accepted)
            rejected.update(page_rejected)
        image_sha = hashlib.sha256(image.read_bytes()).hexdigest()
        for item in accepted:
            candidate_id = f"ogm-ayt:{classification['source_checksum'][:12]}:{number}:{item['source_number']}"
            content.append({"candidate_id": candidate_id, "page": number, "topic": page["topic"], "image_sha256": image_sha, **item})
        rows.append({"page": number, "topic": page["topic"], "image_sha256": image_sha, "accepted_question_count": len(accepted)})
    summary = {"schema": SCHEMA, "source_checksum": classification["source_checksum"], "processed_page_count": len(rows),
               "candidate_count": len(content), "accepted_by_topic": dict(sorted(Counter(item["topic"] for item in content).items())),
               "rejected_reasons": dict(sorted(rejected.items())), "answer_key_accessed": False,
               "solution_text_exported": False, "runtime_enabled": False,
               "notice": "Content-free extraction report. Candidate text stays in the paired private file and needs source-crop, evidence and teacher review."}
    return {"schema": SCHEMA, "source_checksum": classification["source_checksum"], "candidates": content}, {**summary, "pages": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classification", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--content-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--pages", help="Virgülle ayrılmış sayfa numaraları")
    args = parser.parse_args()
    selected = [int(item) for item in args.pages.split(",")] if args.pages else None
    content, report = build(json.loads(args.classification.read_text(encoding="utf-8")), args.image_root, selected)
    for path, value in ((args.content_output, content), (args.report_output, report)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
