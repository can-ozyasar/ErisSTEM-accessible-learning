"""Source-bound question-bank structure and Turkish navigation speech.

This module does not infer answers or image meaning.  Importers may create
drafts, but student delivery requires a reviewed question and reviewed visual
descriptions.  Original PDF text and coordinates remain available for review.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, computed_field, model_validator

from .history_speech import SPOKEN_MUSEUM_NAME, history_spoken_text

AUDIO_TOKEN = re.compile(f"{re.escape(SPOKEN_MUSEUM_NAME)}|\\S+")


class SourceBox(BaseModel):
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float]
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def valid_box(self):
        x0, y0, x1, y1 = self.bbox
        if x0 >= x1 or y0 >= y1:
            raise ValueError("Kaynak kutusu pozitif alana sahip olmalı")
        return self


class Blank(BaseModel):
    number: int = Field(ge=1)
    marker: str = Field(min_length=2)
    source: SourceBox
    reviewed: bool = False


class QuestionPart(BaseModel):
    id: str
    kind: Literal["stem", "prompt", "statement", "caption", "instruction", "choice_table_header"]
    text: str = Field(min_length=1)
    source: SourceBox
    blanks: list[Blank] = []

    @computed_field
    @property
    def spoken_text(self) -> str:
        return spoken_part(self)

    @model_validator(mode="after")
    def blank_order(self):
        numbers = [blank.number for blank in self.blanks]
        if numbers != sorted(set(numbers)):
            raise ValueError("Bölümdeki boşluk numaraları artan ve tekil olmalı")
        for blank in self.blanks:
            if blank.marker not in self.text:
                raise ValueError("Boşluk işareti kaynak metinde bulunmalı")
        return self


class Choice(BaseModel):
    label: Literal["A", "B", "C", "D", "E"]
    text: str = Field(min_length=1)
    source: SourceBox

    @computed_field
    @property
    def spoken_text(self) -> str:
        match = re.fullmatch(r"I:\s*(.+);\s*II:\s*(.+);\s*III:\s*(.+)", self.text)
        if match:
            return history_spoken_text(f"Birinci sütun: {match.group(1)}. İkinci sütun: {match.group(2)}. Üçüncü sütun: {match.group(3)}.")
        return history_spoken_text(self.text)


class QuestionVisual(BaseModel):
    id: str
    kind: Literal["photo", "map", "diagram", "table", "unknown"] = "unknown"
    label: str | None = None
    source: SourceBox
    caption: str | None = None
    description: str | None = None
    description_reviewed: bool = False

    @model_validator(mode="after")
    def reviewed_description_exists(self):
        if self.description_reviewed and not self.description:
            raise ValueError("Onaylı görsel için betimleme gerekli")
        if self.description_reviewed and self.kind == "unknown":
            raise ValueError("Onaylı görselin türü belirlenmeli")
        return self


class Question(BaseModel):
    id: str
    number: int = Field(ge=1)
    question_type: Literal["multiple_choice", "open_response", "fill_blank", "true_false"] = "multiple_choice"
    source: SourceBox
    parts: list[QuestionPart] = Field(min_length=1)
    choices: list[Choice] = []
    visuals: list[QuestionVisual] = []
    status: Literal["draft", "review_required", "approved"] = "draft"
    answer_label: Literal["A", "B", "C", "D", "E"] | None = None
    answer_source_checked: bool = False

    @model_validator(mode="after")
    def valid_structure(self):
        labels = [choice.label for choice in self.choices]
        if self.question_type == "multiple_choice":
            if labels != list("ABCDE"):
                raise ValueError("Çoktan seçmeli soruda A–E şıkları eksiksiz ve sıralı olmalı")
        elif labels:
            raise ValueError("Açık uçlu soruda A–E şıkları bulunmamalı")
        if self.answer_label is not None and self.answer_label not in labels:
            raise ValueError("Cevap mevcut şıklardan biri olmalı")
        if self.status == "approved" and self.answer_label and not self.answer_source_checked:
            raise ValueError("Cevap şıkkı kaynak anahtardan ayrıca doğrulanmalı")
        blanks = [blank.number for part in self.parts for blank in part.blanks]
        if blanks != list(range(1, len(blanks) + 1)):
            raise ValueError("Sorudaki boşluklar 1'den başlayarak sırayla numaralanmalı")
        if self.status == "approved":
            if any(not blank.reviewed for part in self.parts for blank in part.blanks):
                raise ValueError("Onaylı soruda boşluk etiketleri denetlenmeli")
            for part in self.parts:
                source_markers = re.findall(r"-{4,}|_{3,}|\.{5,}", part.text)
                if source_markers != [blank.marker for blank in part.blanks]:
                    raise ValueError("Onaylı soruda kaynak boşluklarının tamamı numaralanmalı")
            if any(not visual.description_reviewed for visual in self.visuals):
                raise ValueError("Onaylı soruda her görselin betimlemesi denetlenmeli")
        return self


def spoken_part(part: QuestionPart) -> str:
    """Read only teacher-marked blanks, never guess that prose ellipsis is blank."""
    text = part.text
    for blank in part.blanks:
        text = text.replace(blank.marker, f" {blank.number}. boşluk ", 1)
    return history_spoken_text(re.sub(r"\s+", " ", text).strip())


def navigation_units(question: Question) -> list[dict[str, str]]:
    """Each question component is independently focusable and speakable."""
    units = [{"id": question.id, "kind": "question", "label": f"Soru {question.number}",
              "spoken_text": f"Soru {question.number}"}]
    body = []
    for part in question.parts:
        label = {"stem": "Soru metni", "prompt": "Soru kökü", "statement": "Önerme",
                 "caption": "Görsel alt yazısı", "instruction": "Yönerge",
                 "choice_table_header": "Şık tablosu sütunları"}[part.kind]
        spoken = spoken_part(part)
        if part.kind == "statement":
            statement = re.match(r"^(I|II|III|IV|V)\.\s*(.*)$", spoken)
            if statement:
                ordinal = {"I": "Birinci", "II": "İkinci", "III": "Üçüncü", "IV": "Dördüncü", "V": "Beşinci"}[statement.group(1)]
                spoken = f"{ordinal} önerme: {statement.group(2)}"
        if part.kind == "choice_table_header":
            spoken = "Seçenek tablosu üç sütunludur: birinci, ikinci ve üçüncü."
        body.append((part.source.page, part.source.bbox[1], part.source.bbox[0],
                     {"id": part.id, "kind": part.kind, "label": label,
                      "spoken_text": spoken if part.kind in {"statement", "choice_table_header"} else f"{label}: {spoken}"}))
    for visual in question.visuals:
        description = visual.description if visual.description_reviewed else "Görsel betimlemesi doğrulanmadı."
        visual_label = f"Görsel {visual.label}" if visual.label else "Görsel"
        spoken_visual_label = {"I": "Birinci görsel", "II": "İkinci görsel", "III": "Üçüncü görsel"}.get(visual.label or "", "Görsel")
        body.append((visual.source.page, visual.source.bbox[1], visual.source.bbox[0],
                     {"id": visual.id, "kind": "visual", "label": visual_label,
                      "spoken_text": history_spoken_text(f"{spoken_visual_label}: {description}")}))
    units.extend(item[3] for item in sorted(body, key=lambda item: item[:3]))
    for choice in question.choices:
        units.append({"id": f"{question.id}-choice-{choice.label}", "kind": "choice",
                      "label": f"Şık {choice.label}", "spoken_text": f"Şık {choice.label}: {choice.spoken_text}"})
    return units


def question_audio_segments(question: Question, limit: int = 80) -> list[dict[str, str]]:
    """Short source-derived speech turns so local TTS can start before a long question finishes."""
    spoken = " ".join(unit["spoken_text"] for unit in navigation_units(question))
    segments = []
    current = ""
    for word in AUDIO_TOKEN.findall(spoken):
        if len(word) > limit:
            raise ValueError("Seslendirme biriminde bölünemeyen uzun sözcük")
        if current and len(current) + len(word) + 1 > limit:
            segments.append({"id": f"segment-{len(segments) + 1}", "spoken_text": current})
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        segments.append({"id": f"segment-{len(segments) + 1}", "spoken_text": current})
    return segments
