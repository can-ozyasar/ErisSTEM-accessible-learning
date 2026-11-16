"""Extract History-1 questions from the private OGM AYT deneme PDF.

This is a discovery-only step.  It never reads answer keys or worked
solutions.  The six section labels are lexical candidates only; PDF evidence
and teacher/agent review remain mandatory before a question is usable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path

import pymupdf

from ..question_bank_extract import extract_book
from ..question_scope import visual_dependency_reasons

DENEME = re.compile(r"(\d+)\.\s*DENEME\b", re.IGNORECASE)

# These are deliberately broad discovery hints, not proof of section
# membership.  Reviewers must confirm the final target section from the PDF.
SECTION_HINTS = {
    "1.3": ("i. dünya savaşı", "birinci dünya savaşı", "çanakkale savaşı", "kafkas cephesi",
            "kanal harekâtı", "kutül amâre", "mondros ateşkes"),
    "2.1": ("millî mücadele", "amasya genelgesi", "erzurum kongresi", "sivas kongresi",
            "havza genelgesi", "misakımillî", "temsil heyeti"),
    "2.4": ("doğu cephesi", "güney cephesi", "gümrü antlaşması", "kars antlaşması",
            "antep savunması", "maraş savunması", "urfa savunması", "kazım karabekir"),
    "2.5": ("batı cephesi", "inönü savaşı", "sakarya savaşı", "büyük taarruz",
            "düzenli ordu", "kütahya eskişehir", "mudanya ateşkes"),
    "3.1": ("atatürk ilkeleri", "cumhuriyetçilik", "halkçılık", "milliyetçilik",
            "devletçilik", "laiklik", "inkılapçılık"),
    "3.2": ("saltanatın kaldırılması", "cumhuriyetin ilanı", "halifeliğin kaldırılması",
            "ankaranın başkent", "siyasi alandaki gelişmeler"),
}


def _question_text(question: dict) -> str:
    return " ".join(part.get("text", "") for part in question.get("parts", []))


def _section_options(text: str) -> list[str]:
    folded = _fold(text)
    return [section for section, hints in SECTION_HINTS.items()
            if any(re.search(r"(?<!\w)" + re.escape(_fold(hint)) + r"(?!\w)", folded)
                   for hint in hints)]


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold().replace("ı", "i"))
    return " ".join("".join(char for char in normalized if not unicodedata.combining(char)).split())


def _is_history_one_page(page: pymupdf.Page) -> bool:
    """Use the printed test header; question numbers repeat in mathematics."""
    header = " ".join(page.get_text("text").splitlines()[:7]).casefold()
    header = header.replace("\u0307", "").replace("ı", "i")
    return ("ayt" in header and "türk dili ve edebiyati" in header
            and "sosyal bilimler-1 testi" in header)


def _choice_letters(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold().replace("ı", "i"))
    return "".join(char for char in folded if char.isalnum() and not unicodedata.combining(char))


def _repair_inline_choice_boxes(question: dict, words: list[tuple]) -> dict | None:
    """Recover A–E cell boxes only when PDF words match all five choices.

    Merged PDF text lines share a single source box. Word geometry gives each
    printed cell its own box; a mismatch leaves the question in manual review.
    """
    qx0, qy0, qx1, qy1 = question["source"]["bbox"]
    within = [word for word in words if qx0 - 1 <= word[0] and word[2] <= qx1 + 1
              and qy0 - 1 <= word[1] and word[3] <= qy1 + 1]
    markers = [word for word in within if re.fullmatch(r"[A-E][).]", word[4].strip())]
    if len(question.get("choices", [])) != 5:
        return None
    revised = deepcopy(question)
    for choice in revised["choices"]:
        label = choice["label"]
        old_y = choice["source"]["bbox"][1]
        matches = [word for word in markers if word[4].strip()[0] == label
                   and abs(word[1] - old_y) < 2]
        if len(matches) != 1:
            return None
        marker = matches[0]
        next_x = min((word[0] for word in markers
                      if abs(word[1] - marker[1]) < 2 and word[0] > marker[0]),
                     default=float("inf"))
        cell = sorted((word for word in within if abs(word[1] - marker[1]) < 2
                       and marker[2] - 0.2 <= word[0] < next_x), key=lambda word: word[0])
        if not cell or _choice_letters(" ".join(word[4] for word in cell)) != _choice_letters(choice["text"]):
            return None
        choice["source"]["bbox"] = [round(marker[0], 2), round(min(word[1] for word in cell), 2),
                                     round(max(word[2] for word in cell), 2),
                                     round(max(word[3] for word in cell), 2)]
    return revised


def build(source: Path, *, denemeler: set[int] | None = None) -> dict:
    raw = source.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    extracted = extract_book(source)
    headings: list[tuple[int, int]] = []
    for page, context in extracted["page_contexts"].items():
        match = DENEME.search(context.get("topic") or "")
        if match:
            headings.append((int(page), int(match.group(1))))
    headings.sort()
    selected = denemeler or {number for _, number in headings}
    ranges: list[tuple[int, int, int]] = []
    for index, (start, number) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else 10**9
        if number in selected:
            ranges.append((start, end, number))

    rows = []
    review_rows = []
    excluded_rows = []
    inline_pages = {int(item["question"]["source"]["page"])
                    for item in extracted["questions"]
                    if "inline_choice_layout_review_required" in item.get("issues", [])}
    with pymupdf.open(source) as pdf:
        history_pages = {index + 1: _is_history_one_page(page) for index, page in enumerate(pdf)}
        history_words = {index + 1: page.get_text("words") for index, page in enumerate(pdf)
                         if index + 1 in inline_pages and history_pages[index + 1]}
    repaired_inline_choices = 0
    for item in extracted["questions"]:
        question = item["question"]
        page = int(question["source"]["page"])
        number = int(question["number"])
        test = next((test for start, end, test in ranges if start <= page < end), None)
        # In this printed test, History-1 occupies questions 25–34; both
        # position and the actual page header must agree.
        if test is None or not history_pages.get(page) or not 25 <= number <= 34:
            continue
        issues = list(item.get("issues", []))
        layout_repair = None
        if "inline_choice_layout_review_required" in issues:
            repaired = _repair_inline_choice_boxes(question, history_words[page])
            if repaired is not None:
                question = repaired
                issues.remove("inline_choice_layout_review_required")
                layout_repair = "pdf_word_geometry_exact_choice_match_v1"
                repaired_inline_choices += 1
        candidate_id = f"ogm-ayt-deneme:{checksum[:12]}:d{test}:p{page}:q{number}"
        visual_reasons = visual_dependency_reasons(question, issues)
        if visual_reasons:
            excluded_rows.append({
                "candidate_id": candidate_id, "page": page, "question_number": number,
                "reasons": visual_reasons, "status": "out_of_scope_visual_question",
            })
            continue
        if question.get("question_type") != "multiple_choice" or issues:
            review_rows.append({
                "candidate_id": candidate_id, "page": page, "question_number": number,
                "source_bbox": question["source"]["bbox"],
                "question": question,
                "issues": issues or ["non_multiple_choice_review_required"],
                "status": "private_pdf_crop_review_required",
            })
            continue
        text = _question_text(question)
        # A distractor can name another unit. Discover sections from the stem
        # only; the answer choices are not evidence of the question's topic.
        options = _section_options(text)
        rows.append({
            "candidate_id": candidate_id,
            "source_kind": "ogm_ayt_tum_dersler_deneme_private",
            "source_checksum": checksum,
            "source_name": source.name,
            "deneme_number": test,
            "page": page,
            "printed_test": "AYT_TDE_SOSYAL_1",
            "target_section_options": options,
            "question": question,
            "layout_repair": layout_repair,
            "transcription_status": "private_teacher_review_required",
            "target_section_status": ("lexical_candidate_requires_review" if options
                                       else "unresolved_section_requires_review"),
            "answer_key_accessed": False,
            "worked_explanation_accessed": False,
        })
    return {
        "schema": "ayt-target-question-candidates-v1",
        "source_checksum": checksum,
        "source_name": source.name,
        "selected_denemeler": sorted(selected),
        "rows": rows,
        "candidate_count": len(rows),
        "review_queue": review_rows,
        "review_count": len(review_rows),
        "scope_exclusions": excluded_rows,
        "scope_excluded_count": len(excluded_rows),
        "inline_choice_geometry_repaired_count": repaired_inline_choices,
        "answer_key_accessed": False,
        "worked_explanation_accessed": False,
        "runtime_enabled": False,
        "qlora_enabled": False,
        "notice": "Private discovery only; target section and PDF evidence review are mandatory.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--denemeler", default="")
    args = parser.parse_args()
    selected = {int(item) for item in args.denemeler.split(",") if item.strip()} or None
    result = build(args.source, denemeler=selected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidate_count": result["candidate_count"],
                      "review_count": result["review_count"],
                      "inline_choice_geometry_repaired_count": result["inline_choice_geometry_repaired_count"],
                      "scope_excluded_count": result["scope_excluded_count"],
                      "denemeler": result["selected_denemeler"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
