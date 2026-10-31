"""Create a balanced, visual-layout verified private AYT candidate pool.

Question text is deliberately not guessed from noisy OCR.  A candidate enters
this pool only after its page image contains an ordered A--E option layout.
It still cannot enter runtime or QLoRA: transcription, MEB evidence and
teacher approval remain separate gates.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

SCHEMA = "ogm-ayt-layout-candidate-pool-v1"
LABEL = re.compile(r"^([A-E])[.)]$")
EXPECTED = tuple("ABCDE")


def _groups(rows: list[dict], width: int) -> list[dict]:
    """Group option labels by column and ordered A--E sequence.

    Reading order is based on y then x, which preserves printed rows such as
    A/B/C on one row and D/E on the next.  Any surplus or malformed label is
    ignored rather than repaired into a question.
    """
    by_column: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        text = row.get("text", "").strip()
        match = LABEL.fullmatch(text)
        if not match or not row.get("left", "").isdigit() or not row.get("top", "").isdigit():
            continue
        by_column[0 if int(row["left"]) < width / 2 else 1].append({
            "label": match.group(1), "left": int(row["left"]), "top": int(row["top"]),
            "width": int(row.get("width", 0) or 0), "height": int(row.get("height", 0) or 0),
        })
    groups = []
    for column, labels in sorted(by_column.items()):
        labels.sort(key=lambda row: (row["top"], row["left"]))
        index, ordinal = 0, 0
        while index + 5 <= len(labels):
            window = labels[index:index + 5]
            if tuple(row["label"] for row in window) != EXPECTED:
                index += 1
                continue
            ordinal += 1
            groups.append({"column": column, "ordinal": ordinal, "labels": window})
            index += 5
    return groups


def _page_groups(image: Path) -> list[dict]:
    merged: list[dict] = []
    # Sparse-text mode recovers labels on pages where a decorative column
    # divider makes the block modes miss one otherwise complete question.
    for mode in (3, 4, 6, 11):
        result = subprocess.run(
            ["tesseract", str(image), "stdout", "-l", "tur", "--psm", str(mode), "tsv"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            raise ValueError(f"Sayfa düzeni OCR başarısız: {image.name}")
        rows = list(csv.DictReader(result.stdout.splitlines(), delimiter="\t"))
        root = next((row for row in rows if row.get("level") == "1"), None)
        if not root or not root.get("width", "").isdigit():
            raise ValueError(f"Sayfa boyutu okunamadı: {image.name}")
        for group in _groups(rows, int(root["width"])):
            first, last = group["labels"][0], group["labels"][-1]
            duplicate = next((item for item in merged if item["column"] == group["column"]
                              and abs(item["labels"][0]["top"] - first["top"]) <= 35
                              and abs(item["labels"][-1]["top"] - last["top"]) <= 35), None)
            if duplicate is None:
                group["ocr_layout_modes"] = [mode]
                merged.append(group)
            else:
                duplicate["ocr_layout_modes"].append(mode)
    for column in (0, 1):
        rows = sorted((row for row in merged if row["column"] == column), key=lambda row: row["labels"][0]["top"])
        for ordinal, row in enumerate(rows, 1):
            row["ordinal"] = ordinal
    return sorted(merged, key=lambda row: (row["column"], row["ordinal"]))


def _balanced_rows(rows: list[dict], target: int) -> list[dict]:
    by_page: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_page[row["page"]].append(row)
    selected, ordered_pages = [], sorted(by_page)
    while len(selected) < target:
        progressed = False
        for page in ordered_pages:
            if by_page[page] and len(selected) < target:
                selected.append(by_page[page].pop(0))
                progressed = True
        if not progressed:
            break
    return selected


def build(scope: dict, image_root: Path, target_per_unit: int = 20,
          target_total: int = 120) -> tuple[dict, dict]:
    if scope.get("schema") != "ogm-ayt-pilot-pool-scope-v1":
        raise ValueError("OGM pilot kapsamı şeması geçersiz")
    if target_per_unit < 1:
        raise ValueError("Her ünite için hedef aday sayısı pozitif olmalı")
    staged: dict[str, list[dict]] = defaultdict(list)
    for unit in scope.get("units", []):
        topic = unit["topic"]
        for page in unit["test_pages"]:
            image = image_root / "pages" / f"{page:03d}.jpg"
            if not image.is_file():
                raise ValueError(f"Test sayfası görüntüsü yok: {page}")
            for group in _page_groups(image):
                staged[topic].append({
                    "candidate_id": f"ogm-layout:{scope['source_checksum'][:12]}:{page}:{group['column']}:{group['ordinal']}",
                    "topic": topic, "page": page,
                    "layout": {"column": group["column"], "option_labels": EXPECTED,
                               "option_label_boxes": group["labels"],
                               "ocr_layout_modes": group["ocr_layout_modes"]},
                    "status": "needs_private_transcription_and_evidence_review",
                })

    if target_total < 1:
        raise ValueError("Toplam hedef aday sayısı pozitif olmalı")
    capacities = {unit["topic"]: len(staged[unit["topic"]]) for unit in scope.get("units", [])}
    if sum(capacities.values()) < target_total:
        raise ValueError(f"Doğrulanmış A-E düzeni toplam hedefi karşılamıyor: {sum(capacities.values())}/{target_total}")
    quotas = {topic: min(target_per_unit, capacity) for topic, capacity in capacities.items()}
    remaining = target_total - sum(quotas.values())
    # The unit short of 20 is never filled by a lower-quality OCR block.  Its
    # small deficit is reallocated only to an already verified surplus.
    for topic in sorted(capacities, key=lambda item: (-(capacities[item] - quotas[item]), item)):
        if not remaining:
            break
        addition = min(remaining, capacities[topic] - quotas[topic])
        quotas[topic] += addition
        remaining -= addition

    selected, unit_report = [], []
    for unit in scope.get("units", []):
        topic = unit["topic"]
        rows = staged[topic]
        balanced = _balanced_rows(rows, quotas[topic])
        selected.extend(balanced)
        unit_report.append({"topic": topic, "layout_verified_count": len(rows), "selected_count": len(balanced),
                            "target_count": quotas[topic]})

    content = {
        "schema": SCHEMA, "source_checksum": scope["source_checksum"], "grade": scope["grade"],
        "candidate_count": len(selected), "candidates": selected,
        "notice": "Private visual-layout candidate pool; contains no answers, solutions or runtime-ready question text.",
    }
    report = {
        "schema": "ogm-ayt-layout-candidate-report-v1", "source_checksum": scope["source_checksum"],
        "candidate_count": len(selected), "target_per_unit": target_per_unit,
        "target_total": target_total, "units": unit_report,
        "answer_key_accessed": False, "solution_text_exported": False, "runtime_enabled": False,
    }
    return content, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--content-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--target-per-unit", type=int, default=20)
    parser.add_argument("--target-total", type=int, default=120)
    args = parser.parse_args()
    content, report = build(
        json.loads(args.scope.read_text(encoding="utf-8")), args.image_root,
        args.target_per_unit, args.target_total,
    )
    for target, body in ((args.content_output, content), (args.report_output, report)):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
