"""Private, layout-bound transcription of visually verified OGM test questions.

This is intentionally a staging tool.  It does not read worked explanations,
answer keys, or correct choices.  Text is accepted only when an already
verified A--E layout provides the boundaries used for OCR.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path

SCHEMA = "ogm-ayt-private-transcription-v1"


def _tsv(image: Path) -> tuple[int, int, list[dict]]:
    result = subprocess.run(
        ["tesseract", str(image), "stdout", "-l", "tur", "--psm", "3", "tsv"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError(f"Soru OCR başarısız: {image.name}")
    rows = list(csv.DictReader(result.stdout.splitlines(), delimiter="\t"))
    root = next((row for row in rows if row.get("level") == "1"), None)
    if not root or not root.get("width", "").isdigit() or not root.get("height", "").isdigit():
        raise ValueError(f"Soru OCR boyutu okunamadı: {image.name}")
    words = []
    for row in rows:
        text = row.get("text", "").strip()
        if text and all(row.get(field, "").isdigit() for field in ("left", "top", "width", "height")):
            words.append({"text": text, **{field: int(row[field]) for field in ("left", "top", "width", "height")}})
    return int(root["width"]), int(root["height"]), words


def _lines(words: list[dict], tolerance: int = 18) -> list[list[dict]]:
    grouped: list[list[dict]] = []
    for word in sorted(words, key=lambda row: (row["top"], row["left"])):
        if not grouped or abs(grouped[-1][0]["top"] - word["top"]) > tolerance:
            grouped.append([word])
        else:
            grouped[-1].append(word)
    return [sorted(line, key=lambda row: row["left"]) for line in grouped]


def _text(words: list[dict]) -> str:
    return " ".join(" ".join(item["text"] for item in line) for line in _lines(words)).strip()


def _candidate_region(candidate: dict, siblings: list[dict], width: int, height: int) -> tuple[int, int, int, int]:
    layout = candidate["layout"]
    labels = layout["option_label_boxes"]
    last_bottom = max(item["top"] + item["height"] for item in labels)
    same_column = sorted((item for item in siblings if item["layout"]["column"] == layout["column"]),
                         key=lambda item: min(box["top"] for box in item["layout"]["option_label_boxes"]))
    index = same_column.index(candidate)
    previous_bottom = 95 if index == 0 else max(
        box["top"] + box["height"] for box in same_column[index - 1]["layout"]["option_label_boxes"]
    )
    next_top = height - 40 if index + 1 == len(same_column) else min(
        box["top"] for box in same_column[index + 1]["layout"]["option_label_boxes"]
    )
    x0, x1 = (0, width // 2) if layout["column"] == 0 else (width // 2, width)
    top = 95 if index == 0 else previous_bottom + 8
    return x0, top, x1, max(next_top - 8, last_bottom + 8)


def _transcribe(candidate: dict, siblings: list[dict], width: int, height: int, words: list[dict]) -> dict:
    x0, y0, x1, y1 = _candidate_region(candidate, siblings, width, height)
    labels = candidate["layout"]["option_label_boxes"]
    option_top = min(label["top"] for label in labels)
    region_words = [word for word in words if x0 <= word["left"] < x1 and y0 <= word["top"] < y1]
    stem = _text([word for word in region_words if word["top"] < option_top - 4])
    choices = []
    by_top: dict[int, list[dict]] = defaultdict(list)
    for label in labels:
        line_top = next((top for top in by_top if abs(top - label["top"]) <= 14), label["top"])
        by_top[line_top].append(label)
    for line_top, line_labels in sorted(by_top.items()):
        line_labels.sort(key=lambda item: item["left"])
        for offset, label in enumerate(line_labels):
            end_x = line_labels[offset + 1]["left"] if offset + 1 < len(line_labels) else x1
            choice_words = [word for word in region_words
                            if abs(word["top"] - label["top"]) <= 28
                            and label["left"] + label["width"] <= word["left"] < end_x]
            choices.append({"label": label["label"], "text": _text(choice_words)})
    labels_seen = [choice["label"] for choice in choices]
    valid = labels_seen == list("ABCDE") and bool(stem) and all(choice["text"] for choice in choices)
    return {"candidate_id": candidate["candidate_id"], "topic": candidate["topic"], "page": candidate["page"],
            "question": {"stem": stem, "choices": choices},
            "source": {"image_sha256": candidate.get("image_sha256"), "layout": candidate["layout"]},
            "transcription_status": "private_teacher_review_required" if valid else "rejected_incomplete_layout_bound_ocr",
            "quality": {"complete_choices": labels_seen == list("ABCDE"), "nonempty_stem": bool(stem),
                        "nonempty_choices": sum(bool(choice["text"]) for choice in choices)},
            "answer_key_accessed": False, "worked_explanation_accessed": False}


def build(pool: dict, image_root: Path) -> tuple[dict, dict]:
    if pool.get("schema") != "ogm-ayt-layout-candidate-pool-v1":
        raise ValueError("Doğrulanmış OGM aday havuzu gerekli")
    by_page: dict[int, list[dict]] = defaultdict(list)
    for candidate in pool.get("candidates", []):
        by_page[candidate["page"]].append(candidate)
    rows = []
    for page, candidates in sorted(by_page.items()):
        width, height, words = _tsv(image_root / "pages" / f"{page:03d}.jpg")
        rows.extend(_transcribe(candidate, candidates, width, height, words) for candidate in candidates)
    accepted = [row for row in rows if row["transcription_status"] == "private_teacher_review_required"]
    report = {"schema": "ogm-ayt-private-transcription-report-v1", "candidate_count": len(rows),
              "accepted_count": len(accepted), "rejected_count": len(rows) - len(accepted),
              "accepted_by_topic": {topic: sum(row["topic"] == topic for row in accepted)
                                    for topic in sorted({row["topic"] for row in rows})},
              "answer_key_accessed": False, "worked_explanation_accessed": False,
              "runtime_enabled": False}
    return {"schema": SCHEMA, "source_checksum": pool["source_checksum"], "rows": rows,
            "notice": "Private staging data; no answer or worked explanation field exists."}, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    content, report = build(json.loads(args.pool.read_text(encoding="utf-8")), args.image_root)
    for target, body in ((args.output, content), (args.report_output, report)):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
