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
from pathlib import Path

from ..question_bank_extract import extract_book

DENEME = re.compile(r"(\d+)\.\s*DENEME\b", re.IGNORECASE)

# These are deliberately broad discovery hints, not proof of section
# membership.  Reviewers must confirm the final target section from the PDF.
SECTION_HINTS = {
    "1.3": ("i. dünya savaşı", "dünya savaşı", "mondros", "osmanlı", "cephe", "seferberlik"),
    "2.1": ("milli mücadele", "millî mücadele", "amasya", "erzurum", "sivas", "tbmm", "meclis"),
    "2.4": ("batı cephesi", "inönü", "sakarya", "büyük taarruz", "düzenli ordu"),
    "2.5": ("doğu cephesi", "güney cephesi", "gümrü", "kars", "antep", "maraş", "urfa"),
    "3.1": ("atatürk ilkeleri", "inkılap", "inkılâp", "anayasa", "hukuk", "eğitim", "kadın"),
    "3.2": ("lozan", "musul", "hatay", "montrö", "balkan", "sadabat", "dış politika", "dış politikası"),
}


def _question_text(question: dict) -> str:
    return " ".join(part.get("text", "") for part in question.get("parts", []))


def _section_options(text: str) -> list[str]:
    folded = " ".join(text.casefold().split())
    return [section for section, hints in SECTION_HINTS.items()
            if any(hint in folded for hint in hints)]


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
    for item in extracted["questions"]:
        question = item["question"]
        page = int(question["source"]["page"])
        number = int(question["number"])
        test = next((test for start, end, test in ranges if start <= page < end), None)
        # In the EA/SÖZ test, History-1 occupies questions 25–34.
        if test is None or not 25 <= number <= 34:
            continue
        if question.get("question_type") != "multiple_choice" or item.get("issues"):
            continue
        text = _question_text(question)
        options = _section_options(text + " " + " ".join(c.get("text", "") for c in question.get("choices", [])))
        rows.append({
            "candidate_id": f"ogm-ayt-deneme:{checksum[:12]}:d{test}:p{page}:q{number}",
            "source_kind": "ogm_ayt_tum_dersler_deneme_private",
            "source_checksum": checksum,
            "source_name": source.name,
            "deneme_number": test,
            "page": page,
            "target_section_options": options,
            "question": question,
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
    print(json.dumps({"candidate_count": result["candidate_count"], "denemeler": result["selected_denemeler"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
