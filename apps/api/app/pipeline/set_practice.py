"""Curated, deterministic set exercises; no OCR or generative grading."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

BANK_VERSION = "sets-grade9-v1"
Operation = Literal["union", "intersection", "difference"]


@dataclass(frozen=True)
class Exercise:
    id: str
    stage: Literal["guided", "transfer"]
    topic: str
    left: tuple[int, ...]
    right: tuple[int, ...]
    operation: Operation
    hints: tuple[str, str, str]


EXERCISES = (
    Exercise("union-guided", "guided", "Birleşim", (1, 2, 4), (2, 3), "union", (
        "Birleşimde, iki kümeden en az birinde bulunan elemanlar alınır.",
        "Önce A'nın, ardından B'nin elemanlarını düşünün.",
        "İki kümede de görünen bir elemanı yalnız bir kez yazın.",
    )),
    Exercise("union-transfer", "transfer", "Birleşim", (0, 2, 5), (2, 6), "union", ("", "", "")),
    Exercise("intersection-guided", "guided", "Kesişim", (1, 2, 4), (2, 3, 4), "intersection", (
        "Kesişimde yalnız iki kümede de bulunan elemanlar alınır.",
        "A'daki her elemanı B'de de arayın.",
        "Yalnızca ortak olanları sonuç kümesine yazın.",
    )),
    Exercise("intersection-transfer", "transfer", "Kesişim", (0, 2, 5), (2, 5, 6), "intersection", ("", "", "")),
    Exercise("difference-guided", "guided", "Fark", (1, 2, 4), (2, 3), "difference", (
        "A fark B, A'da olup B'de olmayan elemanları içerir.",
        "Önce yalnız A'nın elemanlarını ele alın.",
        "B'de de bulunanları A'dan çıkarın; sırayı ters çevirmeyin.",
    )),
    Exercise("difference-transfer", "transfer", "Fark", (0, 2, 5), (2, 6), "difference", ("", "", "")),
)
BY_ID = {exercise.id: exercise for exercise in EXERCISES}


class PublicExercise(BaseModel):
    id: str
    stage: Literal["guided", "transfer"]
    topic: str
    question: str
    spoken_question: str
    answer_format: str = "Örnek giriş: {1, 2, 3}. Boş küme için {} veya ∅ yazın."


class PracticeBank(BaseModel):
    bank_version: str
    title: str
    provenance: str
    exercises: list[PublicExercise]


class AnswerSubmission(BaseModel):
    answer: str = Field(min_length=1, max_length=100)
    attempt: int = Field(ge=1, le=100)


class AnswerFeedback(BaseModel):
    correct: bool
    valid: bool
    message: str
    hint: str | None = None


def expected_answer(exercise: Exercise) -> frozenset[int]:
    left, right = set(exercise.left), set(exercise.right)
    if exercise.operation == "union":
        return frozenset(left | right)
    if exercise.operation == "intersection":
        return frozenset(left & right)
    return frozenset(left - right)


def parse_answer(value: str) -> frozenset[int]:
    value = value.strip()
    if value in ("{}", "∅"):
        return frozenset()
    if value.startswith("{") and value.endswith("}"):
        value = value[1:-1].strip()
    if not value or not re.fullmatch(r"-?\d+(\s*,\s*-?\d+)*", value):
        raise ValueError("invalid_set_format")
    values = [int(part.strip()) for part in value.split(",")]
    if len(values) > 20 or any(abs(number) > 1000 for number in values):
        raise ValueError("invalid_set_size")
    if len(set(values)) != len(values):
        raise ValueError("duplicate_element")
    return frozenset(values)


def public_bank() -> PracticeBank:
    symbols = {"union": ("∪", "birleşim"), "intersection": ("∩", "kesişim"), "difference": ("\\", "fark")}
    items = []
    for exercise in EXERCISES:
        symbol, spoken = symbols[exercise.operation]
        left = ", ".join(map(str, exercise.left))
        right = ", ".join(map(str, exercise.right))
        items.append(PublicExercise(
            id=exercise.id, stage=exercise.stage, topic=exercise.topic,
            question=f"A = {{{left}}}, B = {{{right}}}. A {symbol} B kümesini bulun.",
            spoken_question=f"A kümesi: {left}. B kümesi: {right}. A {spoken} B kümesini bulun.",
        ))
    return PracticeBank(
        bank_version=BANK_VERSION,
        title="9. sınıf kümeler: işlem ve yardımsız tekrar",
        provenance="ErişSTEM tarafından yazılmış sentetik alıştırmalar; MEB kitabından çıkarılmamıştır.",
        exercises=items,
    )


def check_answer(exercise: Exercise, submission: AnswerSubmission) -> AnswerFeedback:
    try:
        answer = parse_answer(submission.answer)
    except ValueError as error:
        message = "Küme biçimini kontrol edin: {1, 2, 3} gibi yazın; elemanları tekrar etmeyin."
        if str(error) == "invalid_set_size":
            message = "Yanıt çok büyük veya sayı aralığı dışında; yalnız sorudaki tam sayıları kullanın."
        return AnswerFeedback(correct=False, valid=False, message=message)
    if answer == expected_answer(exercise):
        return AnswerFeedback(correct=True, valid=True, message="Doğru yanıt.")
    if exercise.stage == "transfer":
        return AnswerFeedback(correct=False, valid=True, message="Henüz doğru değil. Bu soru yardımsız tekrar içindir; yeniden deneyin.")
    hint = exercise.hints[min(submission.attempt - 1, 2)]
    left, right = frozenset(exercise.left), frozenset(exercise.right)
    # Describe a relationship to check, never claim to diagnose the learner's mind.
    if not answer.issubset(left | right):
        hint = "Yanıtta sorudaki iki kümede de bulunmayan eleman var. Her elemanın kaynağını kontrol edin."
    elif exercise.operation == "union" and answer == left & right:
        hint = "Yanıt yalnız ortak elemanları içeriyor. Birleşimde bir kümede bulunmak da yeterli olabilir."
    elif exercise.operation == "intersection" and answer == left | right:
        hint = "Yanıt iki kümenin bütün elemanlarını içeriyor. Kesişim için her elemanın ikisinde de bulunmasını kontrol edin."
    elif exercise.operation == "difference" and answer == right - left:
        hint = "Yanıt B'de olup A'da olmayanları içeriyor. A fark B işleminde başlangıç kümesinin sırasını kontrol edin."
    elif exercise.operation == "difference" and answer & right:
        hint = "Yanıtta B'de de bulunan eleman var. A fark B için A'nın elemanlarının B'de bulunmaması gerekir."
    return AnswerFeedback(correct=False, valid=True, message="Henüz doğru değil. İpucunu kullanarak yeniden deneyin.", hint=hint)
