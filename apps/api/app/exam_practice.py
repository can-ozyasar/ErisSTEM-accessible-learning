"""Procedural practice with sourced annual arrangements, not official exam questions."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from uuid import uuid4

import pymupdf
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .learning_operations import LearningOperationsStore, StrictInput
from .question_scope import visual_dependency_reasons
from .tutor_coach import CoachContext
from .tutor_coach import coach as build_coach_reply

VERIFIED_AT = "2026-10-09"
LGS_SOURCE = "https://odsgm.meb.gov.tr/meb_iys_dosyalar/2026_04/69cfb9daaf8f2557696260_LGS_Basvuru_ve_Uygulama_K%C4%B1lavuzu_2026.pdf"
YKS_SOURCE = "https://dokuman.osym.gov.tr/pdfdokuman/2026/YKS/basvuru_kilavuz06022026.pdf"
EKPSS_SOURCE = "https://dokuman.osym.gov.tr/pdfdokuman/2026/EKPSS/kilavuz_ekpd0402026.pdf"


class ExamSlot(BaseModel):
    id: str
    title: str
    base_minutes: int
    extra_minutes: int


class ExamProfile(BaseModel):
    id: str
    title: str
    year: int = 2026
    verified_at: str = VERIFIED_AT
    source_url: str
    source_section: str
    arrangement: str
    slots: list[ExamSlot]


PROFILES = (
    ExamProfile(id="lgs-reader-2026", title="2026 LGS — total görme yetersizliği düzenlemesi",
                source_url=LGS_SOURCE, source_section="Genel açıklamalar ve 8.1.2",
                arrangement="Okuyucu ve kodlayıcı, tek kişilik salon, 20 dakika ek süre; görsel sorular yerine eş değer sorular.",
                slots=[ExamSlot(id="verbal", title="Sözel oturum", base_minutes=75, extra_minutes=20),
                       ExamSlot(id="numeric", title="Sayısal oturum", base_minutes=80, extra_minutes=20)]),
    ExamProfile(id="yks-reader-2026", title="2026 YKS — okuyucu yardımı alan görme engelli aday",
                source_url=YKS_SOURCE, source_section="Sınav süreleri; 7.11.2 ve 7.11.3",
                arrangement="Bu profil okuyucu yardımı alan görme engelli adaylara ait süreleri gösterir. Diğer yardım/sağlık düzenlemelerine otomatik uygulanmaz.",
                slots=[ExamSlot(id="tyt", title="TYT", base_minutes=165, extra_minutes=30),
                       ExamSlot(id="ayt", title="AYT", base_minutes=180, extra_minutes=50),
                       ExamSlot(id="ydt", title="YDT", base_minutes=120, extra_minutes=60)]),
    ExamProfile(id="ekpss-reader-2026", title="2026 EKPSS — kitapçığı okuyamayan, okuyucu yardımı alan aday",
                source_url=EKPSS_SOURCE, source_section="1.2, 1.4 ve 3.1 sınav süresi tablosu",
                arrangement="Görme engelli grubu: okuyucu veya okuyucu-işaretleyici yardımıyla kitapçığı hiç okuyamayan aday için 40 dakika ek süre.",
                slots=[ExamSlot(id="single", title="Tek oturum", base_minutes=60, extra_minutes=40)]),
    ExamProfile(id="ekpss-self-read-2026", title="2026 EKPSS — soruları kendisi okuyabilen aday",
                source_url=EKPSS_SOURCE, source_section="3.1 sınav süresi tablosu, görme engelli grubu 2b",
                arrangement="Bu alt grupta yalnız işaretleyici yardımı alanlar dahil ek süre yoktur. Az görmeye ilişkin diğer koşullar ayrı alt gruptur.",
                slots=[ExamSlot(id="single", title="Tek oturum", base_minutes=60, extra_minutes=0)]),
)

# Intentionally short, wholly authored material for navigation/reader practice.
TASKS = (
    {"id": "e1", "question": "Bir düzlemde merkeze 4 birim uzaklıktaki bütün noktalar hangi şekli oluşturur?",
     "choices": ["Çember", "Doğru parçası", "Üçgen"], "correct": 0,
     "explanation": "Merkeze eşit uzaklıktaki bütün noktalar çemberi oluşturur."},
    {"id": "e2", "question": "Bir listede elma ve su, diğerinde su ve ekmek var. İki listede de bulunan hangisidir?",
     "choices": ["Elma", "Su", "Ekmek"], "correct": 1,
     "explanation": "Su her iki listede bulunur; ortak elemandır."},
    {"id": "e3", "question": "Yapılacaklar: okuma ve yazma. Tamamlanan: okuma. Henüz tamamlanmamış iş hangisidir?",
     "choices": ["Yazma", "Okuma", "İkisi de tamamlandı"], "correct": 0,
     "explanation": "Yazma yapılacaklar listesinde bulunur, tamamlananlar listesinde bulunmaz."},
    {"id": "e4", "question": "Yarıçapı sıfırdan büyük bir çemberin merkezi çemberin üzerinde midir?",
     "choices": ["Evet", "Yalnız büyükse", "Hayır"], "correct": 2,
     "explanation": "Merkezin kendisine uzaklığı sıfırdır; bu, pozitif yarıçapa eşit değildir."},
    {"id": "e5", "question": "Bir kümede aynı elemanı iki kez yazmak yeni bir eleman ekler mi?",
     "choices": ["Her zaman", "Hayır", "Yalnız eleman sayıysa"], "correct": 1,
     "explanation": "Kümede bir eleman tekrar yazıldığında yeni bir eleman oluşmaz."},
    {"id": "e6", "question": "Kapalı ve köşesiz bir şeklin merkeze uzaklıkları farklı. Bu bilgiler çember olduğunu gösterir mi?",
     "choices": ["Evet, köşesiz olması yeter", "Evet, kapalı olması yeter", "Hayır"], "correct": 2,
     "explanation": "Çember için merkeze eşit uzaklık koşulu da gerekir."},
)
BANK_CHECKSUM = hashlib.sha256(json.dumps(TASKS, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class EvidenceReference(BaseModel):
    """A short, reviewable MEB evidence reference; never a whole source PDF."""

    model_config = ConfigDict(extra="forbid")
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float]
    source_id: str = Field(min_length=8, max_length=80)
    source_kind: Literal["meb_textbook"]
    # PDF atomları bazen birden çok cümle içerir. Runtime record keeps the
    # auditable excerpt; the coach separately bounds what enters an LLM/TTS
    # prompt via ``_short_evidence``.
    quote: str = Field(min_length=8, max_length=2000)
    role: Literal["primary", "context", "relation", "contrast"] = "primary"


class VerifiedMebSource(BaseModel):
    """An official MEB textbook source permitted in a student exam package."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=8, max_length=80)
    kind: Literal["meb_textbook"]
    title: str = Field(min_length=8, max_length=240)
    canonical_url: str = Field(min_length=16, max_length=1000)
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    relative_path: str = Field(min_length=5, max_length=240)
    page_count: int = Field(ge=1, le=600)

    @model_validator(mode="after")
    def official_meb_host(self):
        host = (urlparse(self.canonical_url).hostname or "").lower()
        if not host.endswith((".meb.gov.tr", ".eba.gov.tr")):
            raise ValueError("Kaynak bağlantısı resmî MEB alan adında olmalı")
        path = Path(self.relative_path)
        if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".pdf":
            raise ValueError("Kaynak yolu MEB klasöründeki göreli PDF adı olmalı")
        return self


class AytHistoryQuestion(BaseModel):
    """A reviewed original or locally licensed question accepted by the runtime."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{3,79}$")
    authorship: Literal["original", "licensed_local_pilot", "ai_source_reviewed_local_pilot"]
    # An AI review is useful triage, but it is not sufficient evidence for a
    # student-facing answer key.  Keeping this as a literal makes it
    # impossible to accidentally publish an AI-only candidate pack.
    review_method: Literal["human_pdf_crop_review", "license_bound_pdf_crop_review", "ai_source_consensus_pdf_review"]
    review_artifact_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    topic: str = Field(min_length=2, max_length=160)
    outcome: str = Field(min_length=2, max_length=240)
    split: Literal["development", "retrieval_test", "system_acceptance", "pilot"]
    question: str = Field(min_length=12, max_length=3000)
    spoken_question: str = Field(min_length=12, max_length=3000)
    choices: list[str] = Field(min_length=5, max_length=5)
    correct_label: Literal["A", "B", "C", "D", "E"]
    explanation: str = Field(min_length=12, max_length=1200)
    evidence: list[EvidenceReference] = Field(min_length=1, max_length=3)
    # AI consensus on a larger set does not establish coverage of the final
    # truncated bundle. An independent, bundle-specific gate is required.
    final_bundle_verified: bool = False
    visual_dependency: Literal[False] = False
    visual_description_reviewed: Literal[False] = False
    status: Literal["approved"] = "approved"

    @model_validator(mode="after")
    def safe_for_audio_exam(self):
        if self.authorship == "original" and self.review_method != "human_pdf_crop_review":
            raise ValueError("özgün soru insan PDF kırpımı incelemesiyle onaylanmalı")
        if self.authorship == "licensed_local_pilot" and self.review_method != "license_bound_pdf_crop_review":
            raise ValueError("izinli yerel soru lisans-kayıt bağlı PDF incelemesiyle onaylanmalı")
        if self.authorship == "ai_source_reviewed_local_pilot" and self.review_method != "ai_source_consensus_pdf_review":
            raise ValueError("AI kaynak-doğrulamalı soru AI kaynak uzlaşması incelemesi taşımalı")
        if len({item.strip() for item in self.choices}) != 5 or any(not item.strip() for item in self.choices):
            raise ValueError("Beş benzersiz ve boş olmayan şık gerekli")
        if self.question.lstrip().casefold().startswith("kaynağa göre"):
            raise ValueError("Öğrenciye gösterilen deneme sorusu kaynak metne bağımlı 'Kaynağa göre' köküyle başlayamaz")
        if self.spoken_question.lstrip().casefold().startswith("kaynağa göre"):
            raise ValueError("Öğrenciye dinletilen deneme sorusu kaynak metne bağımlı 'Kaynağa göre' köküyle başlayamaz")
        visual_reasons = visual_dependency_reasons({"stem": self.question, "choices": self.choices})
        if visual_reasons:
            raise ValueError("Görsel veya tabloya bağımlı soru ilk AYT Tarih paketi kapsamı dışında")
        return self


class AytHistoryExamPack(BaseModel):
    """The only non-synthetic AYT package the local student runtime accepts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_name: Literal["ayt-history-exam-pack-v1"] = Field(alias="schema")
    pack_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{3,79}$")
    content_mode: Literal["original_120", "licensed_local_pilot", "ai_source_reviewed_local_pilot"] = "original_120"
    licensed_question_source_checksum: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    license_record_checksum: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    student_publication_allowed: Literal[False] = False
    sources: list[VerifiedMebSource] = Field(min_length=1, max_length=20)
    questions: list[AytHistoryQuestion] = Field(min_length=1, max_length=147)

    @model_validator(mode="after")
    def exactly_one_frozen_split_per_question(self):
        if len({item.id for item in self.questions}) != len(self.questions):
            raise ValueError("Deneme paketinde benzersiz soru kimlikleri gerekli")
        if self.content_mode == "original_120":
            if len(self.questions) != 120 or any(item.authorship != "original" for item in self.questions):
                raise ValueError("özgün paket 120 özgün soru içermeli")
            expected = {"development": 72, "retrieval_test": 24, "system_acceptance": 24}
            actual = {name: sum(item.split == name for item in self.questions) for name in expected}
            if actual != expected:
                raise ValueError("Paket bölümleri 72 geliştirme, 24 retrieval testi ve 24 sistem kabulü olmalı")
        elif self.content_mode == "licensed_local_pilot":
            if (not self.licensed_question_source_checksum or not self.license_record_checksum
                    or any(item.authorship != "licensed_local_pilot" or item.split != "pilot" for item in self.questions)):
                raise ValueError("izinli yerel pilot için lisans zinciri ve yalnız pilot soruları gerekli")
        else:
            allowed = {"licensed_local_pilot", "ai_source_reviewed_local_pilot"}
            if (not self.licensed_question_source_checksum or not self.license_record_checksum
                    or any(item.authorship not in allowed or item.split != "pilot" for item in self.questions)
                    or not any(item.authorship == "ai_source_reviewed_local_pilot" for item in self.questions)):
                raise ValueError("AI kaynak-doğrulamalı pilot için lisans zinciri, yalnız pilot soruları ve en az bir AI denetimli soru gerekli")
        sources = {item.id: item for item in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("Kaynak kataloğunda benzersiz kaynak kimlikleri gerekli")
        for question in self.questions:
            for evidence in question.evidence:
                source = sources.get(evidence.source_id)
                if source is None or source.kind != evidence.source_kind or source.source_checksum != evidence.source_checksum:
                    raise ValueError("Her kanıt paketin doğrulanmış MEB kaynak kataloğuyla eşleşmeli")
        return self


def _task_checksum(tasks: tuple[dict, ...]) -> str:
    return hashlib.sha256(json.dumps(tasks, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def verify_pack_sources(pack: AytHistoryExamPack, source_root: Path) -> None:
    """Bind the authored pack to mounted PDF bytes and page geometry."""
    root = source_root.resolve()
    for source in pack.sources:
        path = (root / source.relative_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Paket kaynağı MEB klasöründe bulunamadı")
        with path.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != source.source_checksum:
                raise ValueError("Paket kaynağı PDF checksum'ı uyuşmuyor")
        with pymupdf.open(path) as pdf:
            if len(pdf) != source.page_count:
                raise ValueError("Paket kaynağı PDF sayfa sayısı uyuşmuyor")
            for question in pack.questions:
                for evidence in question.evidence:
                    if evidence.source_id != source.id:
                        continue
                    if evidence.page > len(pdf):
                        raise ValueError("Kanıt sayfası kaynak PDF dışında")
                    page = pdf[evidence.page - 1]
                    rect = pymupdf.Rect(evidence.bbox)
                    if rect.is_empty or not page.rect.contains(rect):
                        raise ValueError("Kanıt konumu kaynak PDF sayfası dışında")


@lru_cache(maxsize=2)
def active_tasks(pack_path: str = "") -> tuple[dict, ...]:
    """Use the synthetic rehearsal only until a complete reviewed pack is mounted.

    A configured production pack is fail-closed: malformed, partial or
    unreviewed content must never silently fall back to a mixed question set.
    """
    configured = pack_path or os.getenv("AYT_HISTORY_EXAM_PACK", "").strip()
    if not configured:
        return TASKS
    try:
        payload = json.loads(Path(configured).read_text(encoding="utf-8"))
        pack = AytHistoryExamPack.model_validate(payload)
        verify_pack_sources(pack, Path(os.getenv("AYT_HISTORY_SOURCE_ROOT", "data/meb")))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise HTTPException(503, "AYT Tarih deneme paketi geçerli veya hazır değil") from error
    return tuple({"id": item.id, "question": item.question, "spoken_question": item.spoken_question,
                  "choices": item.choices, "correct": "ABCDE".index(item.correct_label),
                  "explanation": item.explanation, "topic": item.topic,
                  "evidence": ([evidence.model_dump() for evidence in item.evidence]
                               if item.authorship != "ai_source_reviewed_local_pilot" or item.final_bundle_verified
                               else [])}
                 for item in pack.questions)


@lru_cache(maxsize=2)
def active_pack_mode(pack_path: str = "") -> str | None:
    """Return only the declared delivery mode, never question or answer data."""
    configured = pack_path or os.getenv("AYT_HISTORY_EXAM_PACK", "").strip()
    if not configured:
        return None
    try:
        payload = json.loads(Path(configured).read_text(encoding="utf-8"))
        return AytHistoryExamPack.model_validate(payload).content_mode
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise HTTPException(503, "AYT Tarih deneme paketi geçerli veya hazır değil") from error


def legacy_ai_task_checksum(tasks: tuple[dict, ...]) -> str | None:
    """Recognize finished sessions from before AI bundle gating, without reopening their evidence."""
    configured = os.getenv("AYT_HISTORY_EXAM_PACK", "").strip()
    if not configured:
        return None
    try:
        pack = AytHistoryExamPack.model_validate_json(Path(configured).read_bytes())
        if pack.content_mode != "ai_source_reviewed_local_pilot":
            return None
        verify_pack_sources(pack, Path(os.getenv("AYT_HISTORY_SOURCE_ROOT", "data/meb")))
        legacy_evidence = {item.id: [ref.model_dump() for ref in item.evidence]
                           for item in pack.questions if item.authorship == "ai_source_reviewed_local_pilot"
                           and not item.final_bundle_verified}
        legacy = tuple({**task, "evidence": legacy_evidence[task["id"]]} if task["id"] in legacy_evidence else task
                       for task in tasks)
        return _task_checksum(legacy) if legacy_evidence else None
    except (OSError, ValueError):
        return None


class ExamCreate(StrictInput):
    profile_id: str
    slot_id: str
    arrangement_confirmed: Literal[True]
    mode: Literal["short", "full"] = "short"
    short_minutes: int = Field(default=5, ge=1, le=60)


class ExamAnswer(StrictInput):
    revision: int = Field(ge=1)
    question_id: str
    answer: str | None
    flagged: bool = False


class ExamCoachTurn(StrictInput):
    revision: int = Field(ge=1)
    turn: int = Field(ge=1, le=2)
    learner_response: str = Field(default="", max_length=1000)
    external_coach_consent: bool = False


class ExamStore:
    def __init__(self, records: LearningOperationsStore):
        self.records = records

    def now(self):
        return datetime.now(UTC).timestamp()

    def tasks(self) -> tuple[dict, ...]:
        return active_tasks()

    def bank_checksum(self) -> str:
        return _task_checksum(self.tasks())

    def availability(self) -> dict:
        """Expose package size and mode for the exam start screen, never answer data."""
        mode = active_pack_mode()
        titles = {
            "original_120": "Özgün AYT Tarih denemesi",
            "licensed_local_pilot": "AYT Tarih yerel pilot paketi",
            "ai_source_reviewed_local_pilot": "AYT Tarih yerel aday paketi",
            None: "Kısa sentetik gezinme provası",
        }
        question_count = len(self.tasks())
        return {
            "title": titles[mode],
            "content_mode": mode,
            "question_count": question_count,
            "session_question_count": question_count,
        }

    def create(self, request: ExamCreate):
        self.cleanup()
        profile = next((item for item in PROFILES if item.id == request.profile_id), None)
        if profile is None:
            raise HTTPException(404, "Sınav profili bulunamadı")
        slot = next((item for item in profile.slots if item.id == request.slot_id), None)
        if slot is None:
            raise HTTPException(422, "Bu profile ait oturum seçin")
        minutes = request.short_minutes if request.mode == "short" else slot.base_minutes + slot.extra_minutes
        started = self.now()
        record = self.records.save(str(uuid4()), "exam", "exam-procedure",
                                   {"profile": profile.model_dump(), "slot": slot.model_dump(),
                                    "mode": request.mode, "duration_minutes": minutes,
                                    "started_at": started, "deadline": started + minutes * 60,
                                    "bank_checksum": self.bank_checksum(), "state": "active",
                                    "answers": {}, "flags": {}, "results": None,
                                    "coach_turns": {}}, 0)
        return self.public(record)

    def get(self, exam_id: str):
        record = self.records.get(exam_id)
        if record is None or "bank_checksum" not in record:
            raise HTTPException(404, "Prova bulunamadı")
        if record["bank_checksum"] != self.bank_checksum():
            if record["state"] != "finished" or record["bank_checksum"] != legacy_ai_task_checksum(self.tasks()):
                raise HTTPException(409, "Soru bankası değişmiş; yeni prova başlatın")
        if record["state"] == "active" and self.now() >= record["deadline"]:
            return self.finish_record(record, "time_expired")
        return record

    def public(self, record: dict):
        tasks = self.tasks()
        pack_mode = active_pack_mode()
        notice = (
            "81 soruluk yerel AYT Tarih pilotu; bazı soruların kaynak değerlendirmesi yapay zekâ ile yapılmıştır. "
            "Kaynak demeti doğrulanmamış sorularda koçluk açılmaz. Aktif sınavda cevap ve çözüm gösterilmez."
            if pack_mode == "ai_source_reviewed_local_pilot" else
            "İzin kaydı, kaynak checksum’ı ve MEB kanıt demetiyle doğrulanmış yerel AYT Tarih pilotu. "
            "Yalnız bu bilgisayardaki gösterim içindir; genel yayın veya resmî sınav eşdeğerliği iddiası değildir. "
            "Aktif sınavda cevap anahtarı, çözüm ve koçluk gösterilmez."
            if pack_mode == "licensed_local_pilot" else
            "Kaynak kataloğu ve checksum ile doğrulanmış özgün AYT Tarih paketi. "
            "Aktif sınavda cevap anahtarı, çözüm ve koçluk gösterilmez."
            if pack_mode == "original_120" else
            "Altı sentetik soruyla süre, okuyucu ve yanıt gezinmesi provasıdır. Resmî soru, tam müfredat denemesi veya gerçek sınavın birebir karşılığı değildir. 2026 profilleri sonraki yıllara uygulanmaz."
        )
        results = record.get("results")
        public_results = None if results is None else []
        for result in results or []:
            task = next((item for item in tasks if item["id"] == result["question_id"]), None)
            revealed = bool(result["correct"] or
                            (task and task.get("evidence") and
                             record.get("coach_turns", {}).get(result["question_id"], 0) >= 2))
            public_results.append({"question_id": result["question_id"],
                                   "answered": result["answered"], "correct": result["correct"],
                                   "correct_answer": result["correct_answer"] if revealed else None,
                                   "explanation": result["explanation"] if revealed else None,
                                   "coach_turns": record.get("coach_turns", {}).get(result["question_id"], 0),
                                   "coach_text": record.get("coach_messages", {}).get(result["question_id"]),
                                   "source_available": bool(task and task.get("evidence"))})
        # The incorrect selection is retained only for the post-exam coach.
        # Never include that server-side working state in public exam payloads.
        visible_record = {key: value for key, value in record.items() if key != "coach_selections"}
        return {**visible_record, "results": public_results,
                "questions": [{"id": task["id"], "question": task.get("spoken_question", task["question"]),
                               "choices": [{"id": f"option-{i+1}", "text": text} for i, text in enumerate(task["choices"])]}
                              for task in tasks],
                "server_now": self.now(),
                "notice": notice}

    def answer(self, exam_id: str, request: ExamAnswer):
        record = self.get(exam_id)
        if record["state"] != "active":
            raise HTTPException(409, "Prova bitmiş; yanıt değiştirilemez")
        task = next((item for item in self.tasks() if item["id"] == request.question_id), None)
        if task is None:
            raise HTTPException(404, "Soru bulunamadı")
        if request.answer is not None and request.answer not in {f"option-{i+1}" for i in range(len(task["choices"]))}:
            raise HTTPException(422, "Geçerli bir seçenek seçin")
        return self.public(self.records.save(exam_id, "exam", "exam-procedure",
                          {**record, "answers": {**record["answers"], request.question_id: request.answer},
                           "flags": {**record["flags"], request.question_id: request.flagged}}, request.revision))

    def finish_record(self, record: dict, reason: str):
        results = []
        coach_selections = {}
        for task in self.tasks():
            answer = record["answers"].get(task["id"])
            expected = f"option-{task['correct']+1}"
            if answer is not None and answer != expected:
                coach_selections[task["id"]] = answer
            results.append({"question_id": task["id"], "answered": answer is not None,
                            "correct": answer == expected, "correct_answer": task["choices"][task["correct"]],
                            "explanation": task["explanation"]})
        return self.records.save(record["id"], "exam", "exam-procedure",
                                 {**record, "state": "finished", "answers": {}, "flags": {}, "coach_selections": coach_selections,
                                  "results": results, "coach_turns": {}, "coach_messages": {},
                                  "finish_reason": reason, "finished_at": self.now()}, record["revision"])

    def finish(self, exam_id: str, revision: int):
        record = self.get(exam_id)
        if record["state"] == "finished":
            return self.public(record)
        if revision != record["revision"]:
            raise HTTPException(409, "Prova değişmiş; kaydı yeniden yükleyin")
        return self.public(self.finish_record(record, "submitted"))

    def coach(self, exam_id: str, question_id: str, request: ExamCoachTurn) -> dict:
        """Post-exam, source-bound deterministic coaching; unavailable during an exam."""
        record = self.get(exam_id)
        if record["state"] != "finished":
            raise HTTPException(409, "Koçluk yalnız deneme tamamlandıktan sonra açılır")
        if request.revision != record["revision"]:
            raise HTTPException(409, "Prova değişmiş; kaydı yeniden yükleyin")
        task = next((item for item in self.tasks() if item["id"] == question_id), None)
        result = next((item for item in record.get("results") or [] if item["question_id"] == question_id), None)
        if task is None or result is None:
            raise HTTPException(404, "Soru bulunamadı")
        evidence = task.get("evidence", [])
        source_ids = [item["source_id"] for item in evidence]
        if result["correct"]:
            raise HTTPException(409, "Doğru yanıt için yanlış soru koçluğu açılmaz")
        if not evidence:
            return {"reply": {"stage": "source_unavailable", "turn": 0,
                    "text": "Bu soru için onaylı kaynak kanıtı yok; kaynaklı koçluk ve çözüm açılmadı.",
                    "source_ids": [], "can_reveal_explanation": False}, "exam": self.public(record)}
        current_turn = record.get("coach_turns", {}).get(question_id, 0)
        if request.turn != current_turn + 1:
            raise HTTPException(409, "Koçluk adımları sırayla açılmalı")
        if request.turn == 2 and not request.learner_response.strip():
            raise HTTPException(422, "İkinci ipucundan önce düşünceni yaz veya söyle")
        selected = record.get("coach_selections", {}).get(question_id)
        choice_ids = [f"option-{i + 1}" for i in range(len(task["choices"]))]
        choice_text = task["choices"][choice_ids.index(selected)] if selected in choice_ids else None
        evidence_by_role: dict[str, str] = {}
        for item in evidence:
            role = item.get("role", "primary")
            quote = item["quote"].strip()
            evidence_by_role[role] = "\n".join(part for part in (evidence_by_role.get(role), quote) if part)
        evidence_text = "\n".join(f"{role}: {quote}" for role, quote in evidence_by_role.items())
        context = CoachContext(
            question_id=question_id,
            question_text=task["question"],
            choice_text=choice_text,
            section_title=task.get("topic", "AYT Tarih"),
            source_ids=source_ids,
            evidence=evidence_text,
            error_type="genel",
            evidence_by_role=evidence_by_role,
        )
        reply = build_coach_reply(
            context,
            # Turn one is a source-bound hint.  The second turn is the
            # deliberate post-hint explanation step; passing the preceding
            # stage is what allows the coach state machine to enter
            # ``gerekceli_aciklama`` rather than restarting at question
            # analysis.
            None if request.turn == 1 else "ogrenci_yaniti",
            request.learner_response,
            request.turn == 2,
            None,
            "ABCDE"[task["correct"]] if request.turn == 2 else None,
            task["choices"][task["correct"]] if request.turn == 2 else None,
        )
        text = reply.student_prompt
        provider = "local"
        if request.turn == 1 and request.external_coach_consent:
            from .deepseek_exam_coach import hint
            generated = hint(context, request.learner_response, task["choices"][task["correct"]])
            if generated:
                text = generated
                provider = "deepseek"
        coach_selections = dict(record.get("coach_selections", {}))
        if request.turn == 2:
            coach_selections.pop(question_id, None)
        updated = self.records.save(exam_id, "exam", "exam-procedure",
                                    {**record, "coach_turns": {**record.get("coach_turns", {}),
                                                               question_id: request.turn},
                                     "coach_selections": coach_selections,
                                     "coach_messages": {**record.get("coach_messages", {}),
                                                        question_id: text}}, record["revision"])
        return {"reply": {"stage": reply.stage, "turn": request.turn,
                "text": text, "source_ids": source_ids, "strategy": reply.strategy,
                "provider": provider,
                "learner_signal": reply.learner_signal, "can_reveal_explanation": reply.can_reveal_explanation},
                "exam": self.public(updated)}

    def remove(self, exam_id: str, revision: int):
        # Do not use get(): expiry must not increment the revision before deletion.
        record = self.records.get(exam_id)
        if record is None or "bank_checksum" not in record:
            raise HTTPException(404, "Prova bulunamadı")
        from sqlalchemy import delete

        from .learning_operations import LearningRecord
        with self.records.sessions() as session:
            result = session.execute(delete(LearningRecord).where(
                LearningRecord.id == exam_id, LearningRecord.revision == revision))
            if result.rowcount != 1:
                raise HTTPException(409, "Prova değişmiş; kaydı yeniden yükleyin")
            session.commit()

    def cleanup(self):
        """Expire abandoned answers and remove exam records after seven days.

        Called on exam use and by the scheduled maintenance command. No learner
        answers or pilot records are printed or exported by maintenance.
        """
        removed = 0
        expired = 0
        for record in self.records.list("exam"):
            try:
                if self.now() - record["started_at"] >= 7 * 86400:
                    self.remove(record["id"], record["revision"])
                    removed += 1
                elif record["state"] == "active" and self.now() >= record["deadline"]:
                    # Source revisions may have changed since the session was started.
                    if record["bank_checksum"] == self.bank_checksum():
                        self.finish_record(record, "time_expired")
                    else:
                        self.records.save(record["id"], "exam", "exam-procedure",
                            {**record, "state": "finished", "answers": {}, "flags": {},
                             "results": [], "finish_reason": "bank_changed", "finished_at": self.now()},
                            record["revision"])
                    expired += 1
            except HTTPException as error:
                if error.status_code != 409:
                    raise
                # A concurrent save/delete won; the next maintenance pass retries.
        return {"removed": removed, "expired": expired}
