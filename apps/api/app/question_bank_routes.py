"""Private question-bank review and approved-question delivery."""

from __future__ import annotations

import os
import re
import time
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import pymupdf
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from .auth import Role, require_roles
from .demo_audio import resolve_demo_audio
from .history_rag import (
    candidate_review_warnings,
    chunk_quality,
    load_index,
    matching_sections,
    rank_chunks,
    recommend_evidence,
)
from .history_source import BOOK as HISTORY_BOOK
from .history_speech import history_spoken_text
from .learning_operations import LearningOperationsStore, LearningRecord
from .local_tts import LocalTtsUnavailable, synthesize_history_text
from .question_bank_extract import extract_book
from .question_bank_structure import Question, navigation_units, question_audio_segments
from .tutor_authoring import create_drafts, infer_error_type, review_draft
from .tutor_coach import CoachContext, coach
from .tutor_dataset import CASES, TutorReviewInput, review_id, validate_review_payload

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
    return (bool(re.search(r"TARİH\s+SORU\s+BANKASI|\b9\.\s*SINIF\b", text, re.IGNORECASE))
            or any(re.fullmatch(answer_cell, value.strip(), re.IGNORECASE) for value in values)
            or len(re.findall(answer_cell, text, re.IGNORECASE)) >= 3)


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


class RagApproval(BaseModel):
    approved: bool
    source_checked: bool
    fact_only_checked: bool
    reason: str = Field(min_length=10, max_length=500)
    expected_revision: int = Field(ge=0)


class EvidenceReview(BaseModel):
    source_ids: list[str] = Field(min_length=1, max_length=2)
    evidence_quality: str = Field(pattern=r"^(direct|partial|insufficient)$")
    visual_dependency: bool
    source_checked: bool
    source_fit_checked: bool
    quality_checked: bool
    approved: bool
    reviewer: str = Field(min_length=2, max_length=80)
    reason: str = Field(min_length=10, max_length=600)
    expected_revision: int = Field(ge=0)


class TutorTurn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(default=None, max_length=80)
    selected_choice: str | None = Field(default=None, pattern=r"^[A-E]$")
    submit_answer: bool = False


def _rag_index():
    try:
        return load_index()
    except (FileNotFoundError, ValueError):
        raise HTTPException(503, "MEB bilgi dizini yok veya kaynak değişmiş; yeniden hazırlayın") from None


def _approved_rag_ids(store, checksum):
    # Legacy approvals remain visible to teachers but cannot enter new reviewed
    # evidence exports until the source-quality check is recorded.
    return {item["chunk_id"] for item in store.list("rag", checksum[:16])
            if item.get("approved") and item.get("quality_checked")
            and item.get("source_checksum") == checksum}


def _evidence_review_id(question_id: str) -> str:
    return f"rag-evidence:{question_id}"


def _student_question(book, store, question_id):
    _candidate(book, question_id)
    record = store.get(_record_id(book["source_checksum"], question_id))
    if not record or record["question"].get("status") != "approved" or _layout_contaminated(record["question"]):
        raise HTTPException(404, "Onaylı soru bulunamadı")
    return Question.model_validate(record["question"])


def _public_question(question):
    # The answer key is a server-side teaching signal, never part of the reading API.
    return question.model_dump(exclude={"answer_label", "answer_source_checked"})


def question_bank_router(store: LearningOperationsStore):
    router = APIRouter(prefix="/v1/question-bank", tags=["question-bank"],
                       dependencies=[Depends(_local_only)])
    teacher = Depends(require_roles(Role.TEACHER, Role.REVIEWER, Role.ADMIN))
    student = Depends(require_roles(Role.STUDENT, Role.TEACHER, Role.REVIEWER, Role.ADMIN))

    @router.get("/teacher/rag/summary")
    def rag_summary(_: Role = teacher):
        index = _rag_index()
        approved = _approved_rag_ids(store, index["source_checksum"])
        legacy = [item for item in store.list("rag", index["source_checksum"][:16])
                  if item.get("approved") and not item.get("quality_checked")]
        return {"source_checksum": index["source_checksum"], "section_count": len(index["sections"]),
                "candidate_count": len(index["chunks"]), "approved_count": len(approved),
                "legacy_recheck_count": len(legacy), "sections": index["sections"]}

    @router.get("/teacher/rag/sections/{section_id}")
    def rag_section(section_id: str, _: Role = teacher):
        index = _rag_index()
        if section_id not in {item["id"] for item in index["sections"]}:
            raise HTTPException(404, "Konu bulunamadı")
        approved = _approved_rag_ids(store, index["source_checksum"])
        return [{**chunk, "approved": chunk["id"] in approved,
                 "quality": chunk.get("quality") or chunk_quality(chunk["text"]),
                 "review_warnings": candidate_review_warnings(chunk["text"]),
                 "revision": (store.get(f"rag:{index['source_checksum'][:12]}:{chunk['id']}") or {}).get("revision", 0)}
                for chunk in index["chunks"] if chunk["section_id"] == section_id]

    @router.put("/teacher/rag/chunks/{chunk_id}")
    def approve_rag_chunk(chunk_id: str, approval: RagApproval, _: Role = teacher):
        index = _rag_index()
        chunk = next((item for item in index["chunks"] if item["id"] == chunk_id), None)
        if not chunk:
            raise HTTPException(404, "Kaynak parçası bulunamadı")
        if approval.approved and (not approval.source_checked or not approval.fact_only_checked):
            raise HTTPException(422, "Metin ve yalnız ders bilgisi içerdiği ayrı ayrı doğrulanmalı")
        return store.save(f"rag:{index['source_checksum'][:12]}:{chunk_id}", "rag",
                          index["source_checksum"][:16],
                          {"chunk_id": chunk_id, "source_checksum": index["source_checksum"],
                           "approved": approval.approved, "quality_checked": approval.source_checked and approval.fact_only_checked,
                           "reason": approval.reason}, approval.expected_revision)

    @router.get("/teacher/rag/chunks/{chunk_id}/preview")
    def rag_chunk_preview(chunk_id: str, _: Role = teacher):
        index = _rag_index()
        chunk = next((item for item in index["chunks"] if item["id"] == chunk_id), None)
        if not chunk:
            raise HTTPException(404, "Kaynak parçası bulunamadı")
        with pymupdf.open(HISTORY_BOOK) as pdf:
            page = pdf[chunk["page"] - 1]
            x0, y0, x1, y1 = chunk["bbox"]
            clip = pymupdf.Rect(max(0, x0 - 8), max(0, y0 - 8),
                                min(page.rect.width, x1 + 8), min(page.rect.height, y1 + 8))
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), clip=clip, alpha=False)
            return Response(pixmap.tobytes("png"), media_type="image/png",
                            headers={"Cache-Control": "private, no-store"})

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

    @router.get("/teacher/tutor/summary")
    def tutor_summary(_: Role = teacher):
        book = _book()
        module_id = book["source_checksum"][:16]
        questions = [item for item in store.list("qb", module_id)
                     if item["question"].get("status") == "approved" and not _layout_contaminated(item["question"])]
        reviewed = [item for item in store.list("tutor_review", module_id) if item.get("approved")]
        groups = {item["question_id"] for item in reviewed}
        complete = {question_id for question_id in groups
                    if {item["case"] for item in reviewed if item["question_id"] == question_id} == set(CASES)}
        return {"approved_questions": len(questions), "approved_examples": len(reviewed),
                "complete_question_groups": len(complete), "required_questions": 120,
                "required_examples": 720, "ready_for_qlora_export": len(complete) >= 120,
                "notice": "Her soru altı koçluk durumuyla incelenir. Kaggle örnekleri kısa, onaylı soru ve MEB kanıtı içerir; cevap anahtarı içermez."}

    def tutor_sources(question):
        index = _rag_index()
        topic = _book()["page_contexts"][question.source.page].get("topic")
        if not matching_sections(index, topic):
            raise HTTPException(422, "Bu soru MEB başlığıyla güvenle eşleşmiyor")
        evidence_review = store.get(_evidence_review_id(question.id))
        if not evidence_review or not evidence_review.get("approved") or evidence_review.get("source_checksum") != index["source_checksum"]:
            raise HTTPException(422, "Bu soru için öğretmen onaylı doğrudan MEB kanıtı henüz seçilmedi")
        allowed_ids = set(evidence_review.get("source_ids", [])) & _approved_rag_ids(store, index["source_checksum"])
        sources = [chunk for chunk in index["chunks"] if chunk["id"] in allowed_ids]
        if len(sources) != len(allowed_ids) or not sources:
            raise HTTPException(422, "Seçilen MEB kanıtı kaynak onayıyla eşleşmiyor")
        return index, sorted(sources, key=lambda item: item["id"])

    @router.get("/teacher/tutor/candidates")
    def tutor_candidates(limit: int = 120, _: Role = teacher):
        if limit < 1 or limit > 120:
            raise HTTPException(422, "İnceleme listesi 1 ile 120 soru arasında olmalı")
        book = _book()
        module_id = book["source_checksum"][:16]
        candidates = []
        for record in store.list("qb", module_id):
            question_payload = record["question"]
            if question_payload.get("status") != "approved" or _layout_contaminated(question_payload):
                continue
            question = Question.model_validate(question_payload)
            evidence_review = store.get(_evidence_review_id(question.id)) or {}
            topic = book["page_contexts"][question.source.page].get("topic") or "Başlık eşleşmedi"
            candidates.append({"question_id": question.id, "number": question.number, "topic": topic,
                               "page": question.source.page, "source_ids": evidence_review.get("source_ids", []),
                               "evidence_reviewed": bool(evidence_review.get("approved")),
                               "drafted_cases": sum(bool(store.get(f"tutor-draft:{question.id}:{case}")) for case in CASES),
                               "reviewed_cases": sum(bool(store.get(review_id(question.id, case))) for case in CASES)})
        # Round-robin topic ordering avoids selecting only the most frequent test section.
        by_topic: dict[str, list[dict]] = {}
        for item in candidates:
            by_topic.setdefault(item["topic"], []).append(item)
        selected = []
        while by_topic and len(selected) < limit:
            for topic in sorted(by_topic):
                if by_topic[topic] and len(selected) < limit:
                    selected.append(by_topic[topic].pop(0))
                if not by_topic[topic]:
                    del by_topic[topic]
        return {"target": 120, "available": len(candidates), "candidates": selected}

    @router.get("/teacher/tutor/questions/{question_id}/source-candidates")
    def tutor_source_candidates(question_id: str, _: Role = teacher):
        """Propose raw PDF passages for review; never enables them for RAG itself."""
        book = _book()
        question = _student_question(book, store, question_id)
        index = _rag_index()
        approved = _approved_rag_ids(store, index["source_checksum"])
        verified_choice = next((choice.text for choice in question.choices if choice.label == question.answer_label),
                               None) if question.answer_source_checked else None
        chosen = recommend_evidence(index, " ".join(part.text for part in question.parts),
                                    [choice.text for choice in question.choices],
                                    book["page_contexts"][question.source.page].get("topic"), limit=12,
                                    verified_choice=verified_choice)
        return {"question_id": question_id,
                "notice": "Bunlar PDF içinden otomatik önerilerdir. Kaynak onayı olmadan öğrenci koçunda veya Kaggle verisinde kullanılamaz.",
                "candidates": [{"id": item["id"], "text": item["text"][:520], "page": item["page"],
                                "section": item["section_title"], "score": item["score"],
                                "evidence_score": item.get("evidence_score"), "signals": item.get("signals", {}),
                                "reasons": item.get("reasons", []), "recommendation": item.get("review_recommendation"),
                                "approved": item["id"] in approved,
                                "review_warnings": candidate_review_warnings(item["text"]),
                                "quality": item.get("quality") or chunk_quality(item["text"])}
                               for item in chosen[:12]]}

    @router.get("/teacher/tutor/questions/{question_id}/evidence-review")
    def get_evidence_review(question_id: str, _: Role = teacher):
        book = _book()
        _student_question(book, store, question_id)
        return store.get(_evidence_review_id(question_id)) or {"question_id": question_id, "status": "not_reviewed"}

    @router.put("/teacher/tutor/questions/{question_id}/evidence-review")
    def save_evidence_review(question_id: str, item: EvidenceReview, _: Role = teacher):
        book = _book()
        _student_question(book, store, question_id)
        index = _rag_index()
        chunks = {chunk["id"]: chunk for chunk in index["chunks"]}
        if len(set(item.source_ids)) != len(item.source_ids) or any(source_id not in chunks for source_id in item.source_ids):
            raise HTTPException(422, "Seçilen MEB kanıt parçaları geçersiz")
        approved_sources = _approved_rag_ids(store, index["source_checksum"])
        if item.approved and (not item.source_checked or not item.source_fit_checked or not item.quality_checked):
            raise HTTPException(422, "Kaynak, soruya uygunluk ve metin kalitesi ayrı ayrı doğrulanmalı")
        if item.approved and (item.evidence_quality != "direct" or item.visual_dependency or not set(item.source_ids) <= approved_sources):
            raise HTTPException(422, "Öğrenci RAG’ı yalnız doğrudan, görsele bağımlı olmayan ve onaylı kanıt kullanabilir")
        payload = {"question_id": question_id, "source_ids": item.source_ids,
                   "evidence_quality": item.evidence_quality, "visual_dependency": item.visual_dependency,
                   "source_checked": item.source_checked, "source_fit_checked": item.source_fit_checked,
                   "quality_checked": item.quality_checked, "approved": item.approved,
                   "reviewer": item.reviewer, "reason": item.reason,
                   "source_checksum": index["source_checksum"]}
        return store.save(_evidence_review_id(question_id), "rag_evidence_review", book["source_checksum"][:16], payload,
                          item.expected_revision)

    @router.get("/teacher/tutor/questions/{question_id}/review")
    def tutor_review_candidate(question_id: str, _: Role = teacher):
        book = _book()
        question = _student_question(book, store, question_id)
        index = _rag_index()
        evidence_review = store.get(_evidence_review_id(question_id)) or {}
        source_ids = set(evidence_review.get("source_ids", []))
        sources = [item for item in index["chunks"] if item["id"] in source_ids]
        return {"question_id": question_id, "question_text": " ".join(part.text for part in question.parts),
                "evidence_review": evidence_review,
                "choices": [{"label": choice.label, "text": choice.text} for choice in question.choices],
                "sources": [{"id": item["id"], "text": item["text"][:520], "page": item["page"],
                             "section": item["section_title"]} for item in sources],
                "cases": [{"case": case, "draft": store.get(f"tutor-draft:{question_id}:{case}"),
                           "review": store.get(review_id(question_id, case))} for case in CASES],
                "notice": "Rehber yanıt öğrencinin söyleyebileceği doğal Türkçe ile yazılmalı; ilk dört durumda cevap veya şık verilmez."}

    @router.post("/teacher/tutor/questions/{question_id}/drafts")
    def create_tutor_drafts(question_id: str, _: Role = teacher):
        book = _book()
        question = _student_question(book, store, question_id)
        index, sources = tutor_sources(question)
        question_text = " ".join(part.text for part in question.parts)
        drafts = create_drafts(question_text, sources)
        saved = []
        for draft in drafts:
            record_id = f"tutor-draft:{question_id}:{draft['case']}"
            current = store.get(record_id)
            payload = {**draft, "question_id": question_id, "question_text": question_text,
                       "source_checksum": index["source_checksum"]}
            saved.append(store.save(record_id, "tutor_draft", book["source_checksum"][:16], payload,
                                    current["revision"] if current else 0))
        return {"question_id": question_id, "drafts": saved}

    @router.post("/teacher/tutor/questions/{question_id}/cases/{case}/agent-review")
    def agent_review_tutor_draft(question_id: str, case: str, candidate: dict | None = None, _: Role = teacher):
        if case not in CASES:
            raise HTTPException(404, "Koçluk durumu bulunamadı")
        draft = store.get(f"tutor-draft:{question_id}:{case}")
        if not draft:
            raise HTTPException(404, "Önce öğretmen taslağı oluşturulmalı")
        if candidate is not None:
            if set(candidate) != {"guide_response"} or not isinstance(candidate["guide_response"], str):
                raise HTTPException(422, "Agent incelemesi yalnız koç metni için istek alır")
            draft = {**draft, "guide_response": candidate["guide_response"].strip()}
        result = review_draft(draft)
        record_id = f"tutor-agent-review:{question_id}:{case}"
        current = store.get(record_id)
        return store.save(record_id, "tutor_agent_review", draft["source_checksum"][:16],
                          {"question_id": question_id, "case": case, "draft_revision": draft["revision"], **result},
                          current["revision"] if current else 0)

    @router.put("/teacher/tutor/reviews/{question_id}/{case}")
    def save_tutor_review(question_id: str, case: str, item: TutorReviewInput, _: Role = teacher):
        if item.question_id != question_id or item.case != case:
            raise HTTPException(409, "URL ile inceleme kaydı eşleşmiyor")
        book = _book()
        question = _student_question(book, store, question_id)
        index, allowed = tutor_sources(question)
        try:
            validate_review_payload(item, {source["id"]: source["text"] for source in allowed})
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        payload = item.model_dump(exclude={"expected_revision"})
        payload.update({"source_checksum": index["source_checksum"], "question_text": " ".join(part.text for part in question.parts)})
        agent = store.get(f"tutor-agent-review:{question_id}:{case}")
        if agent:
            payload["agent_review"] = {key: agent[key] for key in ("passed", "flags", "natural_turkish", "age_appropriate", "early_answer_disclosed")}
        return store.save(review_id(question_id, case), "tutor_review", book["source_checksum"][:16], payload,
                          item.expected_revision)

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
        question = _student_question(book, store, question_id)
        return {"question": _public_question(question), "context": book["page_contexts"][question.source.page],
                "units": navigation_units(question), "audio_segments": question_audio_segments(question)}

    def tutor_data(question_id: str, turn: TutorTurn):
        started = time.monotonic()
        book = _book()
        question = _student_question(book, store, question_id)
        if turn.submit_answer and question.question_type == "multiple_choice" and not turn.selected_choice:
            raise HTTPException(422, "Yanıtını kontrol etmek için bir şık seçmelisin")
        context = book["page_contexts"][question.source.page]
        index = _rag_index()
        topic = context.get("topic")
        section_ids = matching_sections(index, topic)
        if not section_ids:
            text = "Bu testin konusu MEB kitabındaki başlıkla güvenle eşleşmedi. Soru kökünün senden ne istediğini birlikte belirleyelim."
            return {"session_id": turn.session_id or uuid4().hex, "stage": "soru_analizi", "student_prompt": text,
                    "short_spoken_text": text, "error_type": "kaynak_yorumu", "source_ids": [], "abstain_reason": "topic_unmatched",
                    "can_reveal_explanation": False, "sources": [], "timings_ms": {"total": int((time.monotonic() - started) * 1000)}}
        selected = next((choice for choice in question.choices if choice.label == turn.selected_choice), None)
        query = " ".join([turn.message, *(part.text for part in question.parts),
                          selected.text if selected else ""])
        retrieval_started = time.monotonic()
        # A question-specific teacher evidence review is required here.  The
        # answer label stays below this boundary and is never used for retrieval.
        try:
            _, reviewed_sources = tutor_sources(question)
            sources = rank_chunks(reviewed_sources, query, limit=2)
        except HTTPException:
            sources = []
        retrieval_ms = int((time.monotonic() - retrieval_started) * 1000)
        session_id = turn.session_id or uuid4().hex
        prior = store.get(f"tutor:{session_id}") if turn.session_id else None
        if prior and (prior.get("question_id") != question_id or prior.get("source_checksum") != index["source_checksum"]):
            raise HTTPException(409, "Koçluk oturumu bu soru veya kaynak sürümüyle eşleşmiyor")
        if prior and prior.get("turn_count", 0) >= 12:
            raise HTTPException(409, "Bu soru için konuşma sınırına ulaştın")
        previous_stage = prior.get("stage") if prior else None
        repeat_attempts = ((prior or {}).get("repeat_attempts", 0) + 1
                           if turn.selected_choice and (prior or {}).get("last_choice") == turn.selected_choice else 0)
        evidence = sources[0] if sources else None
        answer_choice_text = next((choice.text for choice in question.choices if choice.label == question.answer_label), None)
        coach_context = CoachContext(question_id=question_id,
                                     question_text=" ".join(part.text for part in question.parts),
                                     choice_text=selected.text if selected else None,
                                     section_title=evidence["section_title"] if evidence else "MEB kitabı",
                                     source_ids=[item["id"] for item in sources],
                                     evidence=evidence["text"][:900] if evidence else "",
                                     error_type=infer_error_type(" ".join(part.text for part in question.parts), selected.text if selected else None),
                                     repeat_attempts=repeat_attempts)
        reply = coach(coach_context, previous_stage, turn.message, turn.submit_answer,
                      turn.selected_choice, question.answer_label if question.answer_source_checked else None,
                      answer_choice_text if question.answer_source_checked else None)
        reply.timings_ms.update({"retrieval": retrieval_ms, "request_total": int((time.monotonic() - started) * 1000)})
        store.save(f"tutor:{session_id}", "tutor", index["source_checksum"][:16],
                   {"question_id": question_id, "source_checksum": index["source_checksum"],
                    "stage": reply.stage, "turn_count": (prior or {}).get("turn_count", 0) + 1,
                    "last_choice": turn.selected_choice, "repeat_attempts": repeat_attempts},
                   (prior or {}).get("revision", 0))
        return {"session_id": session_id, **reply.model_dump(),
                "sources": [{"id": item["id"], "page": item["page"], "section": item["section_title"],
                             "section_id": item["section_id"], "bbox": item["bbox"],
                             "excerpt": item["text"][:420]} for item in sources]}

    @router.post("/student/questions/{question_id}/tutor")
    def tutor(question_id: str, turn: TutorTurn, _: Role = student):
        return tutor_data(question_id, turn)

    @router.post("/student/questions/{question_id}/tutor/audio")
    def tutor_audio(question_id: str, turn: TutorTurn, _: Role = student):
        spoken = tutor_data(question_id, turn)["short_spoken_text"]
        try:
            wav = synthesize_history_text(spoken)
        except LocalTtsUnavailable:
            raise HTTPException(503, "Yerel Türkçe ses motoru kullanılamıyor") from None
        return Response(wav, media_type="audio/wav", headers={"Cache-Control": "no-store"})

    @router.get("/student/questions/{question_id}/audio/{unit_id}")
    def student_audio(question_id: str, unit_id: str, _: Role = student):
        book = _book()
        question = _student_question(book, store, question_id)
        units = navigation_units(question)
        segment = next((item for item in question_audio_segments(question) if item["id"] == unit_id), None)
        if segment:
            spoken_text = segment["spoken_text"]
        elif unit_id == "choices":
            selected = [item for item in units if item["kind"] == "choice"]
            spoken_text = "\n".join(item["spoken_text"] for item in selected)
        else:
            unit = next((item for item in units if item["id"] == unit_id), None)
            if not unit:
                raise HTTPException(404, "Okuma birimi bulunamadı")
            spoken_text = unit["spoken_text"]
        try:
            spoken_text = history_spoken_text(spoken_text)
            wav = resolve_demo_audio("question", f"{question_id}:{unit_id}", spoken_text, SOURCE) or synthesize_history_text(spoken_text)
        except LocalTtsUnavailable:
            raise HTTPException(503, "Yerel Türkçe ses motoru kullanılamıyor") from None
        return Response(wav, media_type="audio/wav",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    return router
