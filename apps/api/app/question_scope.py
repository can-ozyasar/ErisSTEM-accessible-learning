"""AYT pilot scope: questions containing visual data are excluded.

This is a product/data selection rule. It does not assert an exam exemption.
Mentioning a historical art form or the word "şekilde" in ordinary prose does
not make the question contain visual data.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

_VISUAL_REFERENCE = re.compile(
    r"\b(?:(?:aşağıda|yukarıda)\s+(?:yer\s+alan|verilen|gösterilen|sunulan)\s+|"
    r"(?:aşağıdaki|yukarıdaki|yandaki|verilen|gösterilen|sunulan)\s+)"
    r"(?:bir\s+)?(?:harita|tablo|çizelge|görsel|resim|fotoğraf|karikatür|grafik|diyagram|şema|şekil)"
    r"[a-zçğıöşü]*\b"
    r"|\b(?:haritada|tabloda|çizelgede|görselde|resimde|fotoğrafta|karikatürde|grafikte|diyagramda|şemada|şekilde)\s+"
    r"(?:gösterilen|verilen|işaretlenen|yer\s+alan|bulunan)\b",
    re.IGNORECASE,
)
_VISUAL_LOCATIVE = re.compile(
    r"\b(?:haritadaki|tablodaki|çizelgedeki|görseldeki|resimdeki|fotoğraftaki|grafikteki|diyagramdaki|şemadaki|şekildeki)\b"
    r"|\b(?:haritada|tabloda|çizelgede|görselde|resimde|fotoğrafta|grafikte|diyagramda|şemada)\b"
    r"|\b(?:haritaya|tabloya|çizelgeye|görsele|resme|fotoğrafa|grafiğe|diyagrama|şemaya|şekle)\s+göre\b",
    re.IGNORECASE,
)
_DEICTIC_VISUAL = re.compile(
    r"\b(?:bu|şu)\s+(?:harita|tablo|çizelge|görsel|resim|fotoğraf|karikatür|grafik|diyagram|şema)"
    r"(?:da|de|ya|ye|ı|i|daki|deki|taki|teki|dan|den)?\b",
    re.IGNORECASE,
)

_ROMAN_PREMISE = re.compile(r"(?<![A-Za-z0-9])(?:I|II|III)(?![A-Za-z0-9])")
_FILL_BLANK = re.compile(r"(?:_{2,}|\.{3,}|……+|boş bırakılan yere|boşluğa)", re.IGNORECASE)
_DATE_OR_CENTURY = re.compile(
    r"\b(?:MÖ\s*)?\d{1,4}(?:\.\s*yüzyıl|\s*yüzyıl|\s*yılında|\s*tarihinde)?\b|"
    r"\b(?:hangi|kaç)\s+yüzyılda\b|"
    r"\b(?:kronolojik|önce|sonra|ardından|sıralama)\b", re.IGNORECASE,
)


@dataclass(frozen=True)
class ScopeDecision:
    eligible: bool
    resolved_section_id: str | None = None
    reasons: tuple[str, ...] = ()
    format_tags: tuple[str, ...] = ()


@dataclass
class AccessibilityAndScopeFilter:
    """Fail-closed pilot gate for visual dependence and target-unit scope.

    Roman-numeral premises, text blanks, and date/century questions are kept
    as supported text formats. The filter rejects only explicit visual
    dependence, embedded visual material, or a question outside the locked
    section/page scope.
    """

    target_section_ids: set[str] = field(default_factory=set)
    page_ranges: tuple[tuple[int, int], ...] = ()
    source_page_ranges: dict[str, tuple[tuple[int, int], ...]] = field(default_factory=dict)

    def __init__(self, target_section_ids: Iterable[str] = (),
                 page_ranges: Iterable[tuple[int, int]] = (),
                 source_page_ranges: dict[str, Iterable[tuple[int, int]]] | None = None):
        self.target_section_ids = set(target_section_ids)
        self.page_ranges = tuple((int(start), int(end)) for start, end in page_ranges)
        self.source_page_ranges = {
            checksum: tuple((int(start), int(end)) for start, end in ranges)
            for checksum, ranges in (source_page_ranges or {}).items()
        }
        if any(start < 1 or end < start for start, end in self.page_ranges):
            raise ValueError("Sayfa kapsamı geçersiz")
        if any(start < 1 or end < start
               for ranges in self.source_page_ranges.values() for start, end in ranges):
            raise ValueError("Kaynağa bağlı sayfa kapsamı geçersiz")

    @staticmethod
    def _question_text(question: dict) -> str:
        parts = [str(question.get("stem", ""))]
        for part in question.get("parts", []) or []:
            if isinstance(part, dict):
                parts.append(str(part.get("text", "")))
        choices = question.get("choices", []) or []
        if isinstance(choices, dict):
            choices = choices.values()
        for choice in choices:
            if isinstance(choice, dict):
                parts.append(str(choice.get("text", "")))
            elif hasattr(choice, "text"):
                parts.append(str(choice.text))
            else:
                parts.append(str(choice))
        return " ".join(parts)

    @staticmethod
    def _format_tags(text: str) -> tuple[str, ...]:
        tags = []
        if _ROMAN_PREMISE.search(text):
            tags.append("roman_numeral_premises")
        if _FILL_BLANK.search(text):
            tags.append("fill_in_the_blank")
        if _DATE_OR_CENTURY.search(text):
            tags.append("date_or_century_chronology")
        return tuple(tags)

    def evaluate(self, question: dict, *, section_id: str | None = None,
                 page: int | None = None, source_checksum: str | None = None,
                 issues: list[str] | None = None) -> ScopeDecision:
        reasons = visual_dependency_reasons(question, issues)
        resolved = section_id or question.get("section_id")
        if self.target_section_ids or self.page_ranges or self.source_page_ranges:
            section_match = resolved in self.target_section_ids if resolved else False
            allowed_ranges = (self.source_page_ranges.get(source_checksum, ())
                              if self.source_page_ranges and source_checksum
                              else self.page_ranges)
            page_match = page is not None and any(start <= page <= end for start, end in allowed_ranges)
            if not (section_match or page_match):
                reasons.append("outside_or_unknown_target_section")
        text = self._question_text(question)
        return ScopeDecision(eligible=not reasons, resolved_section_id=resolved,
                             reasons=tuple(dict.fromkeys(reasons)),
                             format_tags=self._format_tags(text))


def visual_cue_in_text(text: str) -> bool:
    return bool(_VISUAL_REFERENCE.search(text) or _DEICTIC_VISUAL.search(text)
                or _VISUAL_LOCATIVE.search(text))


def visual_dependency_reasons(question: dict, issues: list[str] | None = None) -> list[str]:
    """Return explicit scope reasons; keep prose about images in scope."""
    reasons: list[str] = []
    if question.get("visuals"):
        reasons.append("embedded_visual")
    if "choice_table_review_required" in (issues or []) or any(
        part.get("kind") == "choice_table_header" for part in question.get("parts", [])
    ):
        reasons.append("structured_table")
    text = AccessibilityAndScopeFilter._question_text(question)
    if visual_cue_in_text(text):
        reasons.append("referenced_visual")
    return reasons
