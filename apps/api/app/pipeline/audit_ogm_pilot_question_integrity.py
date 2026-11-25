"""Audit a private OGM pilot against its source records, key, and PDF text layer."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pymupdf

from app.exam_practice import AytHistoryExamPack
from app.question_scope import visual_dependency_reasons


def _tokens(text: str) -> Counter:
    return Counter(re.findall(r"[^\W_]+", re.sub(r"\u00ad\s*", "", text).casefold(), flags=re.UNICODE))


def audit(pack_data: dict, candidates: dict, answers: dict, pdf_path: Path, threshold: float = .9) -> dict:
    if not 0 < threshold <= 1:
        raise ValueError("geçersiz eşik")
    pack = AytHistoryExamPack.model_validate(pack_data)
    source = pack.licensed_question_source_checksum
    if (not source or source != candidates.get("source_checksum") or source != answers.get("source_checksum")
            or candidates.get("schema") != "ayt-target-question-candidates-v1"
            or answers.get("schema") != "ogm-ayt-history-answer-key-v1"):
        raise ValueError("soru ve cevap kaynağı uyuşmuyor")
    with pdf_path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != source:
            raise ValueError("soru PDF checksum uyuşmazlığı")
    rows = candidates.get("rows", [])
    keys = answers.get("records", [])
    by_id = {r["candidate_id"]: r for r in rows}
    answer_by_id = {r["candidate_id"]: r for r in keys}
    if len(by_id) != len(rows) or len(answer_by_id) != len(keys):
        raise ValueError("yinelenen soru veya cevap kimliği")
    id_map = {}
    for identifier in by_id:
        digest = hashlib.sha256(identifier.encode()).hexdigest()[:20]
        id_map["licensed-" + digest] = identifier
        id_map["ai-reviewed-" + digest] = identifier
    results = []
    with pymupdf.open(pdf_path) as pdf:
        for question in pack.questions:
            identifier = id_map.get(question.id)
            if identifier is None or identifier not in answer_by_id:
                raise ValueError("pilot sorusu kaynak veya anahtarda bulunamadı")
            raw = by_id[identifier]["question"]
            parts = raw["parts"]
            choices = raw["choices"]
            stem = "\n\n".join(part.get("text", "").strip() for part in parts if part.get("text", "").strip())
            exact_question = question.question == stem
            exact_choices = [c.get("label") for c in choices] == list("ABCDE") and question.choices == [c.get("text") for c in choices]
            answer_matches = question.correct_label == answer_by_id[identifier].get("correct_choice")
            comparisons = []
            for item in [*parts, *choices]:
                location = item.get("source", {})
                page = location.get("page")
                if location.get("source_checksum") != source or not isinstance(page, int) or not 1 <= page <= len(pdf):
                    raise ValueError("soru parçası PDF kaynağı ile eşleşmiyor")
                rect = pymupdf.Rect(location["bbox"])
                if rect.is_empty or not pdf[page - 1].rect.contains(rect):
                    raise ValueError("soru parçası PDF koordinatı geçersiz")
                words = " ".join(w[4] for w in pdf[page - 1].get_text("words") if pymupdf.Rect(w[:4]).intersects(rect))
                expected = _tokens(item.get("text", "")); actual = _tokens(words)
                total = sum(expected.values())
                comparisons.append(round(sum((expected & actual).values()) / total, 4) if total else 0.0)
            reasons = visual_dependency_reasons({"stem": question.question, "choices": question.choices})
            results.append({"question_id": question.id, "source_candidate_id": identifier,
                            "review_method": question.review_method, "question_exact_match": exact_question,
                            "choices_exact_match": exact_choices, "answer_key_match": answer_matches,
                            "visual_dependency_reasons": reasons, "pdf_text_token_recall": comparisons,
                            "requires_review": not (exact_question and exact_choices and answer_matches and not reasons and all(x >= threshold for x in comparisons))})
    return {"schema": "ogm-pilot-question-integrity-v1", "source_checksum": source,
            "question_count": len(results), "threshold": threshold,
            "requires_review_count": sum(r["requires_review"] for r in results), "questions": results,
            "notice": "PDF text-layer comparison and answer-key consistency only; not visual review or proof of historical correctness."}


def main() -> None:
    parser = argparse.ArgumentParser()
    for option in ("pack", "candidates", "answers", "pdf", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args(); load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    result = audit(load(args.pack), load(args.candidates), load(args.answers), args.pdf)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("question_count", "requires_review_count")}))


if __name__ == "__main__":
    main()
