"""Prepare checksum-bound V5 synthesis input for a published AYT exam pack.

This command deliberately rejects candidate/review queues.  Fine-tuned audio
is expensive to generate and must be attached only to the exact, human
reviewed pack that the student runtime is permitted to open.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from ..exam_practice import AytHistoryExamPack
from ..history_speech import history_spoken_text

SCHEMA = "ayt-history-v5-static-audio-input-v1"
VOICE_MODEL_SHA256 = "8ec3a3312b9586a8650c38d2c8e8e8b6214851f13afbaa935ed4c9d598af8503"

# These are fixed product prompts only.  Learner text, coach replies, answers
# and timer values are intentionally absent: those remain on the fast local
# Piper path at runtime.
INTERFACE_TEXTS = (
    "Kütüphaneye dön.",
    "Provayı başlat.",
    "Önceki soru.",
    "Sonraki soru.",
    "Sorulara git.",
    "Kalan süreyi seslendir.",
    "Soruyu tekrar seslendir.",
    "Şıkları seslendir.",
    "Seçili şıkkı seslendir.",
    "Yanıt seçildi.",
    "Yanıtı kaydetmek için onayla de.",
    "Yanıtı temizlemek için onayla de.",
    "Denemeyi bitirmek ve sonuçları açmak için onayla de.",
    "Onay bekleyen bir sesli işlem yok.",
    "Önce seçtiğin yanıtı onayla veya temizle.",
    "Yanıt ve gözden geçirme işareti kaydedildi.",
    "Bu soru gözden geçirmek için işaretlendi.",
    "Sesi durduruldu.",
)
CHOICE_LABELS = ("A", "B", "C", "D", "E")
_ONES = ("", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz")
_TENS = ("", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan")
_ORDINAL_LAST = ("", "birinci", "ikinci", "üçüncü", "dördüncü", "beşinci", "altıncı", "yedinci", "sekizinci", "dokuzuncu")
_ORDINAL_TENS = ("", "onuncu", "yirminci", "otuzuncu", "kırkıncı", "ellinci", "altmışıncı", "yetmişinci", "sekseninci", "doksanıncı")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_checksum(value: object) -> str:
    return _sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _normalized(value: str) -> str:
    result = history_spoken_text(re.sub(r"\s+", " ", value).strip())
    if not result:
        raise ValueError("empty_spoken_text")
    if len(result) > 8_000:
        raise ValueError("spoken_text_too_long")
    return result


def _question_ordinal(value: int) -> str:
    if not 1 <= value <= 120:
        raise ValueError("question_ordinal_out_of_range")
    hundreds, remainder = divmod(value, 100)
    prefix = "" if not hundreds else ("yüz" if hundreds == 1 else f"{_ONES[hundreds]} yüz")
    tens, one = divmod(remainder, 10)
    if one:
        suffix = " ".join(part for part in (_TENS[tens], _ORDINAL_LAST[one]) if part)
    elif tens:
        suffix = _ORDINAL_TENS[tens]
    else:
        suffix = "yüzüncü"
    return " ".join(part for part in (prefix, suffix) if part)


def build(pack: AytHistoryExamPack, pack_checksum: str) -> dict:
    """Return static utterances, each bound to a stable product unit id."""
    items: list[dict[str, object]] = []

    def add(kind: str, identity: str, role: str, text: str) -> None:
        spoken = _normalized(text)
        items.append({
            "kind": kind,
            "id": identity,
            "static_role": role,
            "spoken_text": spoken,
            "spoken_text_sha256": _sha256_text(spoken),
            # A raw number is not silently sent to V5.  The Kaggle run records
            # it as withheld until its pronunciation has its own review.
            "contains_digits": bool(re.search(r"\d", spoken)),
        })

    for position, question in enumerate(pack.questions, start=1):
        prefix = f"{_question_ordinal(position)} soru. "
        add("question", f"{question.id}:stem", "question_stem", prefix + question.spoken_question)
        for label, choice in zip(CHOICE_LABELS, question.choices, strict=True):
            add("question", f"{question.id}:choice-{label.lower()}", "choice", f"{label} şıkkı. {choice}")
        choices = " ".join(f"{label} şıkkı. {choice}" for label, choice in zip(CHOICE_LABELS, question.choices, strict=True))
        add("question", f"{question.id}:choices", "all_choices", choices)
    for text in INTERFACE_TEXTS:
        add("interface", f"interface:{_sha256_text(text)}", "interface", text)

    keys = [(row["kind"], row["id"]) for row in items]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate_static_audio_unit")
    return {
        "schema_version": SCHEMA,
        "pack_id": pack.pack_id,
        "pack_checksum": pack_checksum,
        "voice_model_sha256": VOICE_MODEL_SHA256,
        "runtime_enabled": False,
        "requires_listener_review": True,
        "notice": "Private Kaggle synthesis input only; this manifest does not publish audio or enable a student runtime.",
        "items": items,
        "summary": {
            "questions": len(pack.questions),
            "static_units": len(items),
            "unique_texts": len({row["spoken_text_sha256"] for row in items}),
            "units_with_digits_withheld": sum(bool(row["contains_digits"]) for row in items),
            "interface_units": len(INTERFACE_TEXTS),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exam-pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing_to_overwrite_v5_static_audio_input")
    raw = args.exam_pack.read_bytes()
    pack = AytHistoryExamPack.model_validate_json(raw)
    payload = build(pack, hashlib.sha256(raw).hexdigest())
    args.output.mkdir(parents=True)
    (args.output / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
