"""Private, metadata-only YKS scope selection.

Official question wording and answer keys never enter this module.  Human
reviewed metadata is sufficient to make the scope decision reproducible.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

WEIGHTS = {"frequency": .40, "evidence": .25, "graph": .20, "accessibility": .15}
YEARS = frozenset(range(2022, 2027))
# AYT Tarih-2 includes 12th-grade Cumhuriyet tarihi content.  Keeping this
# set aligned with the installed MEB corpus prevents a valid AYT tag from
# being rejected before its evidence can be reviewed.
GRADES = frozenset({9, 10, 11, 12})


@dataclass(frozen=True)
class ExamTag:
    exam_id: str
    year: int
    test: str
    question_number: int
    grade: int
    unit_id: str
    concept: str
    relation_type: str
    visual_dependency: bool
    direct_evidence: bool
    accessible: bool
    reviewer: str
    approved: bool

    def validate(self) -> None:
        if self.year not in YEARS or self.test not in {"TYT", "AYT"} or self.grade not in GRADES:
            raise ValueError("YKS metadata kapsamı geçersiz")
        if self.question_number < 1 or not self.unit_id or not self.concept or not self.reviewer:
            raise ValueError("YKS metadata alanları eksik")


def _normalise(values: dict[str, float]) -> dict[str, float]:
    maximum = max(values.values(), default=0)
    return {key: value / maximum if maximum else 0.0 for key, value in values.items()}


def rank_scope(tags: list[ExamTag]) -> dict:
    """Return reproducible class and unit scores from approved metadata only."""
    approved = [tag for tag in tags if tag.approved]
    for tag in approved:
        tag.validate()
    by_grade: dict[int, list[ExamTag]] = defaultdict(list)
    by_unit: dict[tuple[int, str], list[ExamTag]] = defaultdict(list)
    for tag in approved:
        by_grade[tag.grade].append(tag)
        by_unit[(tag.grade, tag.unit_id)].append(tag)
    raw_frequency = {str(grade): len(rows) for grade, rows in by_grade.items()}
    frequency = _normalise(raw_frequency)
    grade_scores = []
    for grade, rows in sorted(by_grade.items()):
        score = (WEIGHTS["frequency"] * frequency[str(grade)] +
                 WEIGHTS["evidence"] * mean(row.direct_evidence for row in rows) +
                 WEIGHTS["graph"] * mean(bool(row.relation_type) for row in rows) +
                 WEIGHTS["accessibility"] * mean(row.accessible and not row.visual_dependency for row in rows))
        grade_scores.append({"grade": grade, "score": round(score, 4), "question_count": len(rows),
                             "components": {"frequency": round(frequency[str(grade)], 4),
                                            "evidence": round(mean(row.direct_evidence for row in rows), 4),
                                            "graph": round(mean(bool(row.relation_type) for row in rows), 4),
                                            "accessibility": round(mean(row.accessible and not row.visual_dependency for row in rows), 4)}})
    grade_scores.sort(key=lambda row: (-row["score"], -row["question_count"], row["grade"]))
    chosen_grade = grade_scores[0]["grade"] if grade_scores else None
    unit_scores = []
    if chosen_grade is not None:
        units = {unit: rows for (grade, unit), rows in by_unit.items() if grade == chosen_grade}
        unit_frequency = _normalise({unit: len(rows) for unit, rows in units.items()})
        for unit, rows in units.items():
            score = (WEIGHTS["frequency"] * unit_frequency[unit] + WEIGHTS["evidence"] * mean(row.direct_evidence for row in rows) +
                     WEIGHTS["graph"] * mean(bool(row.relation_type) for row in rows) +
                     WEIGHTS["accessibility"] * mean(row.accessible and not row.visual_dependency for row in rows))
            unit_scores.append({"unit_id": unit, "score": round(score, 4), "question_count": len(rows)})
    unit_scores.sort(key=lambda row: (-row["score"], -row["question_count"], row["unit_id"]))
    return {"years": sorted(YEARS), "weights": WEIGHTS, "approved_tag_count": len(approved),
            "grade_ranking": grade_scores, "chosen_grade": chosen_grade, "unit_ranking": unit_scores,
            "selected_units": [row["unit_id"] for row in unit_scores[:6]],
            "ready": bool(chosen_grade is not None and len(unit_scores) >= 6)}
