"""Review-gated, source-bound examples for the history coach QLoRA run."""
from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .tutor_coach import ANSWER_LABEL

CASES = (
    "soruyu_anlama", "hatirlayani_ortaya_cikar", "kanitla_bag_kur", "siki_sina",
    "yanlis_cevabi_duzelt", "dogruyu_pekistir",
)
EARLY_ANSWER_CASES = set(CASES[:4])
ERROR_TYPES = ("kisi", "tarih", "yer", "kronoloji", "neden_sonuc", "kaynak_yorumu", "asiri_genelleme", "genel")


class TutorReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question_id: str = Field(min_length=3, max_length=80)
    case: str
    error_type: str
    source_ids: list[str] = Field(min_length=1, max_length=2)
    evidence_quotes: list[str] = Field(min_length=1, max_length=2)
    learner_state: str = Field(min_length=3, max_length=400)
    coaching_goal: str = Field(min_length=8, max_length=300)
    guide_response: str = Field(min_length=10, max_length=600)
    early_answer_disclosed: bool
    grounded_in_source: bool
    simple_turkish: bool
    age_appropriate: bool
    reviewed_by: str = Field(min_length=2, max_length=120)
    approved: bool
    expected_revision: int = Field(ge=0)

    @field_validator("case")
    @classmethod
    def known_case(cls, value: str):
        if value not in CASES:
            raise ValueError("Bilinmeyen koçluk durumu")
        return value

    @field_validator("error_type")
    @classmethod
    def known_error_type(cls, value: str):
        if value not in ERROR_TYPES:
            raise ValueError("Bilinmeyen hata türü")
        return value

    @field_validator("source_ids")
    @classmethod
    def unique_sources(cls, value: list[str]):
        if len(value) != len(set(value)):
            raise ValueError("Kaynak parça kimlikleri tekrarlanamaz")
        return value

    @field_validator("evidence_quotes")
    @classmethod
    def short_quotes(cls, value: list[str]):
        if any(len(item) > 520 for item in value):
            raise ValueError("Kaggle örneğindeki MEB kanıtı 520 karakteri aşamaz")
        return value

    def approved_quality(self) -> bool:
        return self.approved and self.grounded_in_source and self.simple_turkish and self.age_appropriate and not self.early_answer_disclosed


def review_id(question_id: str, case: str) -> str:
    return f"tutor-review-v2:{question_id}:{case}"


def split_question_ids(question_ids: Iterable[str]) -> dict[str, str]:
    ordered = sorted(question_ids, key=lambda item: hashlib.sha256(item.encode("utf-8")).hexdigest())
    if len(ordered) != 120:
        raise ValueError("Bölme işlemi tam 120 soru grubuyla yapılır")
    return {question_id: "train" if index < 84 else "dev" if index < 102 else "sealed_test"
            for index, question_id in enumerate(ordered)}


def validate_review_payload(item: TutorReviewInput, allowed_sources: dict[str, str]) -> None:
    if not set(item.source_ids).issubset(allowed_sources):
        raise ValueError("Seçilen kaynak parçası bu sorunun onaylı getirme sonucunda yok")
    if len(item.source_ids) != len(item.evidence_quotes):
        raise ValueError("Her kaynak kimliği için bir kısa MEB kanıtı gerekli")
    if any(quote not in allowed_sources[source_id] for source_id, quote in zip(item.source_ids, item.evidence_quotes)):
        raise ValueError("MEB kanıtı seçilen kaynak parçasından birebir alınmalı")
    if item.approved and not item.approved_quality():
        raise ValueError("Onay için kaynak bağlılık, sade Türkçe, yaş düzeyi ve cevap ifşası kontrolleri olumlu olmalı")
    if item.case in EARLY_ANSWER_CASES and ANSWER_LABEL.search(item.guide_response):
        raise ValueError("Bu aşamada rehber yanıt cevap veya şık ifşa edemez")


def export_rows(records: Iterable[dict]) -> tuple[dict[str, list[dict]], dict]:
    approved = [item for item in records if item.get("approved")]
    by_question: dict[str, dict[str, dict]] = {}
    for item in approved:
        by_question.setdefault(item["question_id"], {})[item["case"]] = item
    complete = {key: value for key, value in by_question.items() if set(value) == set(CASES)}
    if len(complete) < 120:
        raise ValueError("Dışa aktarma için altı durumu da onaylı en az 120 soru gerekir")
    selected_ids = sorted(complete)[:120]
    rows = {"train": [], "dev": [], "sealed_test": []}
    for question_id, split in split_question_ids(selected_ids).items():
        for case in CASES:
            item = complete[question_id][case]
            prompt = "\n".join((
                "Sen 9. sınıf tarih soru koçusun. Öğrenciyi düşündür; kısa ve doğal Türkçe kullan.",
                "Cevabı veya doğru şıkkı, öğrenci denemeden açıklama.",
                f"Koçluk durumu: {case}", f"Hata türü: {item['error_type']}",
                f"Soru: {item['question_text']}", f"Öğrenci: {item['learner_state']}",
                "MEB kanıtı: " + " ".join(item["evidence_quotes"]), "Koç:"))
            rows[split].append({"group_id": question_id, "case": case, "error_type": item["error_type"],
                                "prompt": prompt, "completion": item["guide_response"]})
    counts = Counter(row["group_id"] for bucket in rows.values() for row in bucket)
    if len(counts) != 120 or any(count != 6 for count in counts.values()):
        raise ValueError("Aynı sorunun altı turu tek veri bölümünde kalmalı")
    return rows, {"question_groups": 120, "examples": 720,
                  "splits": {key: len(value) for key, value in rows.items()},
                  "contains_short_reviewed_evidence": True, "contains_answer_keys": False}
