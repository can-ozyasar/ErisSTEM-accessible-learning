"""Private review records and safe QLoRA export for the history coach.

The export deliberately contains coaching behaviour only.  It must never
contain MEB PDF text, question-bank text, answer labels, page coordinates or
student records; factual grounding remains an inference-time RAG concern.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .tutor_coach import ANSWER_LABEL

REVIEW_STAGES = ("soru_analizi", "kanit_bulma", "sik_elemesi")


class TutorReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question_id: str = Field(min_length=3, max_length=80)
    stage: str
    source_ids: list[str] = Field(min_length=1, max_length=3)
    guide_response: str = Field(min_length=10, max_length=600)
    early_answer_disclosed: bool
    grounded_in_source: bool
    simple_turkish: bool
    reviewed_by: str = Field(min_length=2, max_length=120)
    approved: bool
    expected_revision: int = Field(ge=0)

    @field_validator("stage")
    @classmethod
    def known_stage(cls, value: str):
        if value not in REVIEW_STAGES:
            raise ValueError("Bu eğitim setinde yalnız ilk üç rehberlik aşaması incelenir")
        return value

    @field_validator("source_ids")
    @classmethod
    def unique_sources(cls, value: list[str]):
        if len(value) != len(set(value)):
            raise ValueError("Kaynak parça kimlikleri tekrarlanamaz")
        return value

    def approved_quality(self) -> bool:
        return self.approved and self.grounded_in_source and self.simple_turkish and not self.early_answer_disclosed


def review_id(question_id: str, stage: str) -> str:
    return f"tutor-review:{question_id}:{stage}"


def split_question_ids(question_ids: Iterable[str]) -> dict[str, str]:
    """Stable grouped 42/9/9 split; all turns of a question share one split."""
    ordered = sorted(question_ids, key=lambda item: hashlib.sha256(item.encode("utf-8")).hexdigest())
    if len(ordered) != 60:
        raise ValueError("Bölme işlemi tam 60 soru grubuyla yapılır")
    return {question_id: "train" if index < 42 else "dev" if index < 51 else "sealed_test"
            for index, question_id in enumerate(ordered)}


def validate_review_payload(item: TutorReviewInput, allowed_source_ids: set[str]) -> None:
    if not set(item.source_ids).issubset(allowed_source_ids):
        raise ValueError("Seçilen kaynak parçası bu sorunun onaylı getirme sonucunda yok")
    if item.approved and not item.approved_quality():
        raise ValueError("Onay için kaynak bağlılık, sade Türkçe ve cevap ifşası kontrolleri olumlu olmalı")
    if item.approved and ANSWER_LABEL.search(item.guide_response):
        raise ValueError("İlk üç aşamadaki rehber yanıtı cevap veya şık ifşa edemez")


def export_rows(records: Iterable[dict]) -> tuple[dict[str, list[dict]], dict]:
    """Return non-copyrighted protocol data after checking the 60x3 gate."""
    approved = [item for item in records if item.get("approved")]
    by_question: dict[str, dict[str, dict]] = {}
    for item in approved:
        by_question.setdefault(item["question_id"], {})[item["stage"]] = item
    complete = {key: value for key, value in by_question.items() if set(value) == set(REVIEW_STAGES)}
    if len(complete) < 60:
        raise ValueError("Dışa aktarma için üç aşaması da onaylı en az 60 soru gerekir")
    selected_ids = sorted(complete)[:60]
    rows = {"train": [], "dev": [], "sealed_test": []}
    splits = split_question_ids(selected_ids)
    for question_id in selected_ids:
        split = splits[question_id]
        for stage in REVIEW_STAGES:
            item = complete[question_id][stage]
            prompt = (
                "Sen kaynak bağlı 9. sınıf tarih soru koçusun. Cevabı açıklama; sade Türkçe ipucu ver.\n"
                f"Aşama: {stage}\nSoru ve MEB kanıtı çalışma anında sağlanacaktır.\nKoç:"
            )
            rows[split].append({
                "group_id": question_id,
                "stage": stage,
                "prompt": prompt,
                "completion": item["guide_response"],
            })
    counts = Counter(row["group_id"] for bucket in rows.values() for row in bucket)
    if any(count != 3 for count in counts.values()):
        raise ValueError("Aynı sorunun turları farklı veri bölümlerine ayrılamaz")
    return rows, {"question_groups": len(selected_ids), "examples": sum(len(value) for value in rows.values()),
                  "splits": {key: len(value) for key, value in rows.items()},
                  "contains_source_material": False, "contains_answer_keys": False}
