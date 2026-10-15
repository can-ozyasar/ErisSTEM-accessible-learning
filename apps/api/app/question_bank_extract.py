"""Conservative candidate extraction for the local Vip history question bank.

No candidate is published by this module.  It records source coordinates and
explicit issues for teacher review, including missing choices and visuals.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .question_bank_structure import Question
from .question_bank_visual_proposals import proposal as visual_proposal

QUESTION_START = re.compile(r"^([1-9][0-9]?)\.\s*(.*)$")
CHOICE_START = re.compile(r"^([A-E])\)\s*(.*)$")
STATEMENT_START = re.compile(r"^(I|II|III|IV|V)\.\s*(.*)$")
BLANK_MARKER = re.compile(r"-{4,}|_{3,}|\.{5,}")
TEST_HEADING = re.compile(r"^(Kavrama|Geliştirme|Vip|VİP|Tarama)\s+Testi\s*-\s*(\d{1,2})$", re.I)
NUMBERED_TEST = re.compile(r"^Test\s*-\s*(\d{1,2})$", re.I)
ANSWER_KEY_CELL = re.compile(r"^\d{1,2}\s*[-–.]\s*[A-E]$", re.I)


@dataclass(frozen=True)
class Line:
    text: str
    bbox: tuple[float, float, float, float]
    bold: bool
    horizontal: bool = True


def _box(lines):
    return (round(min(line.bbox[0] for line in lines), 2),
            round(min(line.bbox[1] for line in lines), 2),
            round(max(line.bbox[2] for line in lines), 2),
            round(max(line.bbox[3] for line in lines), 2))


def _join(lines):
    result = ""
    for line in lines:
        value = line.text.replace("\x07", "").strip()
        if not value:
            continue
        if result.endswith("\xad") or (result.endswith("-") and value[:1].islower()):
            result = result[:-1] + value
        else:
            result += (" " if result else "") + value
    return re.sub(r"\s+", " ", result.replace("\xad", "")).strip()


def _fold(value: str) -> str:
    return value.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")).casefold()


def _all_page_lines(page):
    lines = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for raw in block["lines"]:
            spans = raw["spans"]
            value = "".join(span["text"] for span in spans)
            if not value.strip():
                continue
            substantial = [span for span in spans if span["text"].strip()]
            bold = bool(substantial) and sum("Bold" in span["font"] for span in substantial) >= len(substantial) / 2
            direction = raw.get("dir", (1, 0))
            lines.append(Line(value, tuple(raw["bbox"]), bold,
                              direction[0] > 0.9 and abs(direction[1]) < 0.1))
    return lines


def _answer_key_lines(lines: list[Line], height: float) -> set[int]:
    """Find compact answer-key strips by repeated number-letter cells, not a page number."""
    matches = [(index, line) for index, line in enumerate(lines)
               if line.horizontal and ANSWER_KEY_CELL.fullmatch(line.text.strip())]
    excluded = set()
    for index, line in matches:
        peers = [(other_index, other) for other_index, other in matches
                 if abs(other.bbox[1] - line.bbox[1]) < 5]
        if len(peers) >= 3 and (line.bbox[1] < height * 0.2 or line.bbox[1] > height * 0.8):
            excluded.update(other_index for other_index, _ in peers)
    # Some books stack the key in a narrow side strip instead of a row.
    if len(matches) >= 4:
        for index, line in matches:
            peers = [(other_index, other) for other_index, other in matches
                     if abs(other.bbox[0] - line.bbox[0]) < 20
                     and abs(other.bbox[1] - line.bbox[1]) < height * 0.2]
            if len(peers) >= 4 and (line.bbox[1] < height * 0.2 or line.bbox[1] > height * 0.75):
                excluded.update(other_index for other_index, _ in peers)
    return excluded


def page_lines(page):
    """Keep question text, never page furniture or rotated publisher marks."""
    height = page.rect.height
    raw = _all_page_lines(page)
    key_lines = _answer_key_lines(raw, height)
    return [line for index, line in enumerate(raw)
            if line.horizontal and line.bbox[1] >= 55 and line.bbox[3] <= height - 35
            and index not in key_lines
            and not re.fullmatch(r"\d{1,2}\.\s*sinif", _fold(line.text.strip()))
            and not (line.bbox[1] > height * 0.88 and ANSWER_KEY_CELL.fullmatch(line.text.strip()))]


def extract_page_context(page, page_number: int, checksum: str):
    """Read the visible heading as navigation metadata, not as question prose."""
    raw = [line for line in _all_page_lines(page) if line.horizontal]
    midpoint = page.rect.width / 2
    starts = [line.bbox[1] for line in raw if QUESTION_START.match(line.text.strip())
              and (line.bbox[0] < 70 or midpoint < line.bbox[0] <= midpoint + 40)]
    limit = min(min(starts) - 8 if starts else page.rect.height * 0.22,
                page.rect.height * 0.22)
    header = sorted((line for line in raw if line.bbox[1] < limit and line.bbox[3] < limit + 12),
                    key=lambda line: (line.bbox[1], line.bbox[0]))
    test_name = None
    test_number = None
    for line in header:
        value = re.sub(r"\s+", " ", line.text).strip()
        match = TEST_HEADING.fullmatch(value)
        if match:
            kind = _fold(match.group(1))
            test_name = {"vip": "VIP Testi", "gelistirme": "Geliştirme Testi"}.get(kind, f"{kind.capitalize()} Testi")
            test_number = int(match.group(2))
            break
        match = NUMBERED_TEST.fullmatch(value)
        if match:
            test_name, test_number = "Tarama Testi", int(match.group(1))
            break
    if test_name is None:
        words = {_fold(line.text.strip()) for line in header}
        test_kind = next((kind for kind in ("kavrama", "gelistirme", "vip", "tarama")
                          if kind in words or f"{kind} testi" in words), None)
        if test_kind and ("testi" in words or f"{test_kind} testi" in words):
            numbers = [int(line.text.strip()) for line in header
                       if line.text.strip().isdigit() and 1 <= int(line.text.strip()) <= 99]
            if numbers:
                test_name = {"vip": "VIP Testi", "gelistirme": "Geliştirme Testi"}.get(test_kind, f"{test_kind.capitalize()} Testi")
                test_number = numbers[0]
        elif "alistirmalar" in words:
            test_name = "Alıştırmalar"
    candidates = []
    for line in header:
        value = re.sub(r"\s+", " ", line.text).strip()
        simple = _fold(value)
        if not value or value.isdigit() or TEST_HEADING.fullmatch(value) or NUMBERED_TEST.fullmatch(value):
            continue
        if simple in {"kavrama", "gelistirme", "tarama", "vip testi", "testi", "alistirmalar", "bolum"}:
            continue
        if re.match(r"^(unite\s*[-–]?\s*\d+|\d+\.\s*sinif)$", simple):
            continue
        if len(value) >= 8:
            candidates.append(line)
    # A chapter opener may lack a topic. Do not invent one; extract_book may
    # inherit it only from the facing page with the exact same test identity.
    topic_lines = sorted(candidates, key=lambda line: (line.bbox[1], line.bbox[0]))
    topic = _join(topic_lines) if topic_lines else None
    source = _source(page_number, _box(topic_lines if topic_lines else header), checksum) if header else None
    return {"topic": topic, "test_name": test_name, "test_number": test_number,
            "source": source}


def _column(line, midpoint):
    return 0 if (line.bbox[0] + line.bbox[2]) / 2 < midpoint else 1


def _source(page_number, bbox, checksum):
    return {"page": page_number, "bbox": bbox, "source_checksum": checksum}


def _part(part_id, kind, lines, page_number, checksum, blank_start):
    text = _join(lines)
    blanks = []
    for index, match in enumerate(BLANK_MARKER.finditer(text), blank_start):
        blanks.append({"number": index, "marker": match.group(),
                       "source": _source(page_number, _box(lines), checksum),
                       "reviewed": False})
    return {"id": part_id, "kind": kind, "text": text,
            "source": _source(page_number, _box(lines), checksum), "blanks": blanks}


def _parse_question(lines, images, page_number, column, checksum):
    start = lines[0]
    match = QUESTION_START.match(start.text.strip())
    number = int(match.group(1))
    question_id = f"p{page_number}-c{column+1}-q{number}"
    # Number can be on its own PDF line, followed by stem text at the same y.
    content = []
    if match.group(2):
        content.append(Line(match.group(2), start.bbox, start.bold))
    content.extend(lines[1:])
    body = []
    choices: dict[str, list[Line]] = {}
    current_choice = None
    for line in content:
        stripped = line.text.strip()
        option = CHOICE_START.match(stripped)
        if option:
            current_choice = option.group(1)
            choices.setdefault(current_choice, []).append(Line(option.group(2), line.bbox, line.bold))
        elif current_choice and line.bbox[1] - choices[current_choice][-1].bbox[3] <= 6:
            # A wrapped option stays with the nearest option in the same x lane.
            same_row = [key for key, value in choices.items()
                        if abs(value[-1].bbox[1] - line.bbox[1]) < 4]
            if same_row:
                current_choice = min(same_row, key=lambda key: abs(choices[key][0].bbox[0] - line.bbox[0]))
            choices[current_choice].append(line)
        elif not choices:
            body.append(line)
        else:
            # Text after options is ambiguous and must be checked by a teacher.
            body.append(line)
    parts = []
    pending = []
    pending_kind = "stem"
    def flush():
        nonlocal pending
        if pending and _join(pending):
            parts.append(_part(f"{question_id}-part-{len(parts)+1}", pending_kind,
                               pending, page_number, checksum,
                               1 + sum(len(part["blanks"]) for part in parts)))
        pending = []
    for line in body:
        value = line.text.strip()
        if STATEMENT_START.match(value):
            flush()
            pending_kind = "statement"
            pending.append(line)
        elif pending_kind == "statement" and pending and abs(line.bbox[1] - pending[-1].bbox[1]) < 4:
            pending.append(line)
        elif line.bold and pending and not pending[-1].bold and not STATEMENT_START.match(value):
            flush()
            pending_kind = "prompt"
            pending.append(line)
        elif pending_kind == "statement" and pending and line.bbox[1] - pending[-1].bbox[3] > 7:
            flush()
            pending_kind = "prompt"
            pending.append(line)
        else:
            pending.append(line)
    flush()
    table_headers = [part for part in parts if part["kind"] == "statement" and
                     re.fullmatch(r"(?:I|II|III)\.", part["text"])]
    table_choice_layout = len(table_headers) == 3 and [part["text"] for part in table_headers] == ["I.", "II.", "III."]
    if table_choice_layout:
        first = table_headers[0]["source"]["bbox"]
        last = table_headers[-1]["source"]["bbox"]
        parts = [part for part in parts if part not in table_headers]
        parts.append({"id": f"{question_id}-table-header", "kind": "choice_table_header",
                      "text": "I, II ve III", "source": _source(page_number,
                      (first[0], first[1], last[2], last[3]), checksum), "blanks": []})
    options = []
    unlabeled_horizontal_cells = False
    for label in "ABCDE":
        if label not in choices:
            continue
        option_lines = choices[label]
        if not table_choice_layout and len(option_lines) > 1 and any(
            abs(line.bbox[1] - option_lines[0].bbox[1]) < 3 and line.bbox[0] - option_lines[0].bbox[2] > 8
            for line in option_lines[1:]
        ):
            unlabeled_horizontal_cells = True
        if table_choice_layout and len(option_lines) == 3 and all(abs(line.bbox[1] - option_lines[0].bbox[1]) < 3 for line in option_lines):
            value = "; ".join(f"{header}: {_join([line])}" for header, line in zip(("I", "II", "III"), option_lines))
        elif len(option_lines) > 1 and all(abs(line.bbox[1] - option_lines[0].bbox[1]) < 3 for line in option_lines):
            names = ("Birinci sütun", "İkinci sütun", "Üçüncü sütun", "Dördüncü sütun", "Beşinci sütun")
            value = "; ".join(f"{names[index]}: {_join([line])}" for index, line in enumerate(option_lines))
        else:
            value = _join(option_lines)
        if value:
            options.append({"label": label, "text": value,
                            "source": _source(page_number, _box(option_lines), checksum)})
    x0 = 0 if column == 0 else 320
    x1 = 320 if column == 0 else 641
    y0 = start.bbox[1]
    y1 = max(line.bbox[3] for line in lines)
    visuals = []
    relevant_images = []
    for block in images:
        b = block["bbox"]
        area = (b[2] - b[0]) * (b[3] - b[1])
        if area < 2500 or not (x0 <= (b[0] + b[2]) / 2 < x1) or not (y0 <= (b[1] + b[3]) / 2 <= y1):
            continue
        relevant_images.append(block)
    for index, block in enumerate(sorted(relevant_images, key=lambda item: (round(item["bbox"][1] / 10), item["bbox"][0])), 1):
        b = block["bbox"]
        label = ("I", "II", "III", "IV", "V")[index - 1] if len(relevant_images) > 1 and index <= 5 else None
        suggested = visual_proposal(checksum, page_number, number, index)
        visuals.append({"id": f"{question_id}-visual-{index}", "kind": suggested[0] if suggested else "unknown",
                        "label": label,
                        "source": _source(page_number, tuple(round(z, 2) for z in b), checksum),
                        "caption": None, "description": suggested[1] if suggested else None,
                        "description_reviewed": False})
    issues = []
    if any("\x07" in line.text for line in lines):
        issues.append("pdf_control_character_review_required")
    if any(ANSWER_KEY_CELL.fullmatch(line.text.strip()) for line in lines):
        issues.append("possible_answer_key_in_question_review_required")
    labels = [option["label"] for option in options]
    all_text = " ".join(part["text"] for part in parts).lower()
    if choices:
        question_type = "multiple_choice"
    elif "doğru olanlara" in all_text and "yanlış olanlara" in all_text:
        question_type = "true_false"
    elif "boş bırakılan" in all_text or any(part["blanks"] for part in parts):
        question_type = "fill_blank"
    else:
        question_type = "open_response"
    if choices and (labels != list("ABCDE") or len(choices) != 5):
        issues.append("choices_incomplete_or_out_of_order")
    if not choices:
        issues.append("non_multiple_choice_review_required")
    if not parts:
        issues.append("question_text_missing")
    if visuals:
        issues.append("visual_description_required")
    if table_choice_layout:
        issues.append("choice_table_review_required")
    if unlabeled_horizontal_cells:
        issues.append("horizontal_choice_cells_review_required")
    if any(part["blanks"] for part in parts):
        issues.append("blank_review_required")
    payload = {"id": question_id, "number": number, "question_type": question_type,
               "source": _source(page_number, (x0, round(y0, 2), x1, round(y1, 2)), checksum),
               "parts": parts, "choices": options, "visuals": visuals,
               "status": "review_required" if issues else "draft"}
    try:
        Question.model_validate(payload)
    except Exception:
        if "structure_invalid" not in issues:
            issues.append("structure_invalid")
    return {"question": payload, "issues": issues}


def extract_page(page, page_number: int, checksum: str):
    midpoint = page.rect.width / 2
    lines = page_lines(page)
    images = [block for block in page.get_text("dict")["blocks"] if block["type"] == 1]
    results = []
    for column in (0, 1):
        ordered = sorted((line for line in lines if _column(line, midpoint) == column),
                         key=lambda line: (line.bbox[1], line.bbox[0]))
        starts = [index for index, line in enumerate(ordered)
                  if QUESTION_START.match(line.text.strip())
                  and (line.bbox[0] < 70 if column == 0 else 325 <= line.bbox[0] <= 360)]
        for pos, index in enumerate(starts):
            end = starts[pos + 1] if pos + 1 < len(starts) else len(ordered)
            results.append(_parse_question(ordered[index:end], images, page_number, column, checksum))
    # On two-column test pages, read the left column to its end before the right.
    return sorted(results, key=lambda item: (item["question"]["source"]["bbox"][0],
                                             item["question"]["source"]["bbox"][1]))


def extract_book(path: Path):
    content = path.read_bytes()
    checksum = hashlib.sha256(content).hexdigest()
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        pages = [extract_page(page, index + 1, checksum) for index, page in enumerate(pdf)]
        contexts = {index + 1: extract_page_context(page, index + 1, checksum)
                    for index, page in enumerate(pdf)}
    for number, context in contexts.items():
        if context["topic"] or not context["test_name"] or not context["test_number"]:
            continue
        for neighbor in (number + 1, number - 1):
            other = contexts.get(neighbor)
            if other and other["topic"] and (other["test_name"], other["test_number"]) == (context["test_name"], context["test_number"]):
                context["topic"] = other["topic"]
                context["topic_source"] = other["source"]
                break
    return {"source_checksum": checksum, "page_count": len(pages),
            "page_contexts": contexts,
            "questions": [item for page in pages for item in page]}
