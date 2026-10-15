"""Private question-bank review and approved-question delivery."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import pymupdf
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from .auth import Role, require_roles
from .learning_operations import LearningOperationsStore, LearningRecord
from .local_tts import LocalTtsUnavailable, synthesize_verified_text
from .question_bank_extract import extract_book
from .question_bank_structure import Question, navigation_units

SOURCE = Path("/private/question-bank/vip-9-sinif-tarih-soru-bankasi.pdf")


def _local_only():
    if os.getenv("APP_ENV", "development") == "production":
        raise HTTPException(503, "Soru bankası telif ve kimlik doğrulama kararı olmadan üretime açılamaz")


@lru_cache(maxsize=2)
def _load(mtime_ns: int, size: int):
    if size < 1 or size > 75 * 1024 * 1024:
        raise HTTPException(413, "Soru bankası PDF boyutu desteklenen sınırda değil")
    result = extract_book(SOURCE)
    if result["page_count"] > 300:
        raise HTTPException(413, "Soru bankası sayfa sınırını aşıyor")
    return result


def _book():
    try:
        stat = SOURCE.stat()
    except FileNotFoundError:
        raise HTTPException(503, "Soru bankası PDF'si bulunamadı") from None
    return _load(stat.st_mtime_ns, stat.st_size)


def _record_id(checksum: str, question_id: str):
    return f"qb-v1:{checksum[:12]}:{question_id}"


def _candidate(book, question_id: str):
    result = next((item for item in book["questions"] if item["question"]["id"] == question_id), None)
    if result is None:
        raise HTTPException(404, "Soru bulunamadı")
    return result


def _layout_contaminated(question: dict) -> bool:
    values = [*(part.get("text", "") for part in question.get("parts", [])),
              *(choice.get("text", "") for choice in question.get("choices", []))]
    text = " ".join(values)
    answer_cell = r"\b\d{1,2}\s*[-–]\s*[A-E]\b"
    return (bool(re.search(r"TARİH\s+SORU\s+BANKASI|\b9\.\s*SINIF\b", text, re.I))
            or any(re.fullmatch(answer_cell, value.strip(), re.I) for value in values)
            or len(re.findall(answer_cell, text, re.I)) >= 3)


class QuestionUpdate(BaseModel):
    question: Question
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=500)


class PageApproval(BaseModel):
    question_ids: list[str] = Field(min_length=1)
    source_checked: bool
    choices_checked: bool
    reading_order_checked: bool
    reason: str = Field(min_length=10, max_length=500)


def question_bank_router(store: LearningOperationsStore):
    router = APIRouter(prefix="/v1/question-bank", tags=["question-bank"],
                       dependencies=[Depends(_local_only)])
    teacher = Depends(require_roles(Role.TEACHER, Role.REVIEWER, Role.ADMIN))
    student = Depends(require_roles(Role.STUDENT, Role.TEACHER, Role.REVIEWER, Role.ADMIN))

    @router.get("/teacher/summary")
    def summary(_: Role = teacher):
        book = _book()
        module = book["source_checksum"][:16]
        reviews = store.list("qb", module)
        approved = sum(item["question"]["status"] == "approved" and not _layout_contaminated(item["question"]) for item in reviews)
        quarantined = sum(item["question"]["status"] == "approved" and _layout_contaminated(item["question"]) for item in reviews)
        return {"page_count": book["page_count"], "candidate_count": len(book["questions"]),
                "approved_count": approved, "quarantined_count": quarantined,
                "source_checksum": book["source_checksum"],
                "notice": "Vip Yayınları telifli PDF: yalnız yerel öğretmen incelemesi."}

    @router.get("/teacher/pages/{page_number}")
    def teacher_page(page_number: int, _: Role = teacher):
        book = _book()
        if page_number < 1 or page_number > book["page_count"]:
            raise HTTPException(404, "Sayfa bulunamadı")
        items = []
        for candidate in book["questions"]:
            if candidate["question"]["source"]["page"] != page_number:
                continue
            review = store.get(_record_id(book["source_checksum"], candidate["question"]["id"]))
            stored = review["question"] if review else candidate["question"]
            contaminated = _layout_contaminated(stored)
            items.append({"question": stored,
                          "issues": [*candidate["issues"], *(["approved_page_furniture_review_required"] if contaminated else [])],
                          "source_candidate": candidate["question"] if contaminated else None,
                          "revision": review["revision"] if review else 0,
                          "review_reason": review.get("reason") if review else None})
        return {"page": page_number, "context": book["page_contexts"][page_number], "questions": items}

    @router.get("/teacher/questions/{question_id}/preview")
    def preview(question_id: str, _: Role = teacher):
        book = _book()
        candidate = _candidate(book, question_id)["question"]
        page_number = candidate["source"]["page"]
        with pymupdf.open(SOURCE) as pdf:
            page = pdf[page_number - 1]
            x0, y0, x1, y1 = candidate["source"]["bbox"]
            clip = pymupdf.Rect(max(0, x0 - 8), max(0, y0 - 7),
                                min(page.rect.width, x1 + 8), min(page.rect.height, y1 + 7))
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.7, 1.7), clip=clip, alpha=False)
            return Response(pixmap.tobytes("png"), media_type="image/png",
                            headers={"Cache-Control": "private, no-store"})

    @router.get("/teacher/pages/{page_number}/image")
    def teacher_page_image(page_number: int, _: Role = teacher):
        book = _book()
        if page_number < 1 or page_number > book["page_count"]:
            raise HTTPException(404, "Sayfa bulunamadı")
        with pymupdf.open(SOURCE) as pdf:
            pixmap = pdf[page_number - 1].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            return Response(pixmap.tobytes("png"), media_type="image/png",
                            headers={"Cache-Control": "private, no-store"})

    @router.post("/teacher/pages/{page_number}/approve-clean")
    def approve_clean_page(page_number: int, approval: PageApproval, _: Role = teacher):
        book = _book()
        if page_number < 1 or page_number > book["page_count"]:
            raise HTTPException(404, "Sayfa bulunamadı")
        if not (approval.source_checked and approval.choices_checked and approval.reading_order_checked):
            raise HTTPException(422, "Kaynak, şıklar ve okuma sırası ayrı ayrı doğrulanmalı")
        clean = [item["question"] for item in book["questions"]
                 if item["question"]["source"]["page"] == page_number and not item["issues"]]
        if not clean or set(approval.question_ids) != {item["id"] for item in clean} or len(approval.question_ids) != len(clean):
            raise HTTPException(409, "Sayfanın uyarısız soru listesi değişti; yeniden yükleyin")
        records = []
        for payload in clean:
            question = Question.model_validate({**payload, "status": "approved"})
            records.append(LearningRecord(
                id=_record_id(book["source_checksum"], question.id), kind="qb",
                module_id=book["source_checksum"][:16], revision=1,
                payload={"question": question.model_dump(), "reason": approval.reason,
                         "review_scope": "page_clean_batch"},
            ))
        with store.sessions() as session:
            try:
                session.add_all(records)
                session.commit()
            except IntegrityError:
                session.rollback()
                raise HTTPException(409, "Sorulardan biri daha önce düzenlenmiş veya onaylanmış; sayfayı yeniden yükleyin") from None
        return {"approved_count": len(records), "question_ids": [item.id for item in records]}

    @router.put("/teacher/questions/{question_id}")
    def save(question_id: str, update: QuestionUpdate, _: Role = teacher):
        book = _book()
        candidate = _candidate(book, question_id)["question"]
        question = update.question
        if question.id != question_id or question.source.source_checksum != book["source_checksum"]:
            raise HTTPException(409, "Soru veya kaynak sürümü eşleşmiyor")
        if question.status == "approved" and _layout_contaminated(question.model_dump()):
            raise HTTPException(422, "Sayfa alt bilgisi soru metninde; kaynakla düzeltmeden onaylanamaz")
        if question.source.page != candidate["source"]["page"] or question.number != candidate["number"]:
            raise HTTPException(422, "Soru numarası ve sayfası değiştirilemez")
        if any(part.source.source_checksum != book["source_checksum"] or part.source.page != question.source.page
               for part in question.parts):
            raise HTTPException(422, "Soru bölümü kaynağa bağlı olmalı")
        if any(choice.source.source_checksum != book["source_checksum"] or choice.source.page != question.source.page
               for choice in question.choices):
            raise HTTPException(422, "Şık kaynağa bağlı olmalı")
        if any(visual.source.source_checksum != book["source_checksum"] or visual.source.page != question.source.page
               for visual in question.visuals):
            raise HTTPException(422, "Görsel kaynağa bağlı olmalı")
        original_visuals = {visual["id"]: visual["source"]["bbox"] for visual in candidate["visuals"]}
        reviewed_visuals = {visual.id: list(visual.source.bbox) for visual in question.visuals}
        if reviewed_visuals != original_visuals or len(question.visuals) != len(original_visuals):
            raise HTTPException(422, "Kaynak görsel çıkarılamaz veya başka bölgeye taşınamaz")
        record = store.save(_record_id(book["source_checksum"], question_id), "qb",
                            book["source_checksum"][:16],
                            {"question": question.model_dump(), "reason": update.reason},
                            update.expected_revision)
        return record

    @router.get("/student/questions")
    def student_catalog(_: Role = student):
        book = _book()
        records = store.list("qb", book["source_checksum"][:16])
        published = [Question.model_validate(item["question"]) for item in records
                     if item["question"].get("status") == "approved" and not _layout_contaminated(item["question"])]
        return [{"id": item.id, "number": item.number, "page": item.source.page,
                 "question_type": item.question_type, "context": book["page_contexts"][item.source.page]}
                for item in sorted(published, key=lambda q: (q.source.page, q.source.bbox[0], q.source.bbox[1]))]

    @router.get("/student/questions/{question_id}")
    def student_question(question_id: str, _: Role = student):
        book = _book()
        _candidate(book, question_id)
        record = store.get(_record_id(book["source_checksum"], question_id))
        if not record or record["question"].get("status") != "approved" or _layout_contaminated(record["question"]):
            raise HTTPException(404, "Onaylı soru bulunamadı")
        question = Question.model_validate(record["question"])
        return {"question": question.model_dump(), "context": book["page_contexts"][question.source.page],
                "units": navigation_units(question)}

    @router.get("/student/questions/{question_id}/audio/{unit_id}")
    def student_audio(question_id: str, unit_id: str, _: Role = student):
        book = _book()
        _candidate(book, question_id)
        record = store.get(_record_id(book["source_checksum"], question_id))
        if not record or record["question"].get("status") != "approved" or _layout_contaminated(record["question"]):
            raise HTTPException(404, "Onaylı soru bulunamadı")
        question = Question.model_validate(record["question"])
        unit = next((item for item in navigation_units(question) if item["id"] == unit_id), None)
        if not unit:
            raise HTTPException(404, "Okuma birimi bulunamadı")
        try:
            wav = synthesize_verified_text(unit["spoken_text"])
        except LocalTtsUnavailable:
            raise HTTPException(503, "Yerel Türkçe ses motoru kullanılamıyor") from None
        return Response(wav, media_type="audio/wav",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    return router
