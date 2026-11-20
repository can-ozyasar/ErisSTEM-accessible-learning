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

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .learning_operations import LearningOperationsStore, StrictInput
from .question_scope import visual_dependency_reasons

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
    quote: str = Field(min_length=8, max_length=700)
    role: Literal["primary", "context", "relation", "contrast"] = "primary"


class VerifiedMebSource(BaseModel):
    """An official MEB textbook source permitted in a student exam package."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=8, max_length=80)
    kind: Literal["meb_textbook"]
    title: str = Field(min_length=8, max_length=240)
    canonical_url: str = Field(min_length=16, max_length=1000)
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(ge=1, le=600)

    @model_validator(mode="after")
    def official_meb_host(self):
        host = (urlparse(self.canonical_url).hostname or "").lower()
        if not (host.endswith(".meb.gov.tr") or host == "ogmmateryal.eba.gov.tr"):
            raise ValueError("Kaynak bağlantısı resmî MEB alan adında olmalı")
        return self


class AytHistoryQuestion(BaseModel):
    """Private authored question accepted by the student exam runtime."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{3,79}$")
    authorship: Literal["original"]
    review_method: Literal["ai_source_text_review", "human_pdf_crop_review"]
    review_artifact_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    topic: str = Field(min_length=2, max_length=160)
    outcome: str = Field(min_length=2, max_length=240)
    split: Literal["development", "retrieval_test", "system_acceptance"]
    question: str = Field(min_length=12, max_length=3000)
    spoken_question: str = Field(min_length=12, max_length=3000)
    choices: list[str] = Field(min_length=5, max_length=5)
    correct_label: Literal["A", "B", "C", "D", "E"]
    explanation: str = Field(min_length=12, max_length=1200)
    evidence: list[EvidenceReference] = Field(min_length=1, max_length=3)
    visual_dependency: Literal[False] = False
    visual_description_reviewed: Literal[False] = False
    status: Literal["approved"] = "approved"

    @model_validator(mode="after")
    def safe_for_audio_exam(self):
        if len(set(item.strip() for item in self.choices)) != 5 or any(not item.strip() for item in self.choices):
            raise ValueError("Beş benzersiz ve boş olmayan şık gerekli")
        visual_reasons = visual_dependency_reasons({"stem": self.question, "choices": self.choices})
        if visual_reasons:
            raise ValueError("Görsel veya tabloya bağımlı soru ilk AYT Tarih paketi kapsamı dışında")
        return self


class AytHistoryExamPack(BaseModel):
    """The only non-synthetic AYT package the local student runtime accepts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_name: Literal["ayt-history-exam-pack-v1"] = Field(alias="schema")
    pack_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{3,79}$")
    sources: list[VerifiedMebSource] = Field(min_length=1, max_length=20)
    questions: list[AytHistoryQuestion] = Field(min_length=120, max_length=120)

    @model_validator(mode="after")
    def exactly_one_frozen_split_per_question(self):
        if len({item.id for item in self.questions}) != 120:
            raise ValueError("Deneme paketinde 120 benzersiz soru gerekli")
        expected = {"development": 72, "retrieval_test": 24, "system_acceptance": 24}
        actual = {name: sum(item.split == name for item in self.questions) for name in expected}
        if actual != expected:
            raise ValueError("Paket bölümleri 72 geliştirme, 24 retrieval testi ve 24 sistem kabulü olmalı")
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
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise HTTPException(503, "AYT Tarih deneme paketi geçerli veya hazır değil") from error
    return tuple({"id": item.id, "question": item.question, "spoken_question": item.spoken_question,
                  "choices": item.choices, "correct": "ABCDE".index(item.correct_label),
                  "explanation": item.explanation, "topic": item.topic,
                  "evidence": [evidence.model_dump() for evidence in item.evidence]}
                 for item in pack.questions)


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


class ExamStore:
    def __init__(self, records: LearningOperationsStore):
        self.records = records

    def now(self):
        return datetime.now(UTC).timestamp()

    def tasks(self) -> tuple[dict, ...]:
        return active_tasks()

    def bank_checksum(self) -> str:
        return _task_checksum(self.tasks())

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
                                    "answers": {}, "flags": {}, "results": None}, 0)
        return self.public(record)

    def get(self, exam_id: str):
        record = self.records.get(exam_id)
        if record is None or "bank_checksum" not in record:
            raise HTTPException(404, "Prova bulunamadı")
        if record["bank_checksum"] != self.bank_checksum():
            raise HTTPException(409, "Soru bankası değişmiş; yeni prova başlatın")
        if record["state"] == "active" and self.now() >= record["deadline"]:
            return self.finish_record(record, "time_expired")
        return record

    def public(self, record: dict):
        tasks = self.tasks()
        is_production_pack = bool(os.getenv("AYT_HISTORY_EXAM_PACK", "").strip())
        notice = (
            "Kaynak kataloğu ve checksum ile doğrulanmış özgün AYT Tarih paketi. "
            "Aktif sınavda cevap anahtarı, çözüm ve koçluk gösterilmez."
            if is_production_pack else
            "Altı sentetik soruyla süre, okuyucu ve yanıt gezinmesi provasıdır. Resmî soru, tam müfredat denemesi veya gerçek sınavın birebir karşılığı değildir. 2026 profilleri sonraki yıllara uygulanmaz."
        )
        return {**record,
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
        for task in self.tasks():
            answer = record["answers"].get(task["id"])
            expected = f"option-{task['correct']+1}"
            results.append({"question_id": task["id"], "answered": answer is not None,
                            "correct": answer == expected, "correct_answer": task["choices"][task["correct"]],
                            "explanation": task["explanation"]})
        return self.records.save(record["id"], "exam", "exam-procedure",
                                 {**record, "state": "finished", "answers": {}, "flags": {},
                                  "results": results, "finish_reason": reason, "finished_at": self.now()}, record["revision"])

    def finish(self, exam_id: str, revision: int):
        record = self.get(exam_id)
        if record["state"] == "finished":
            return self.public(record)
        if revision != record["revision"]:
            raise HTTPException(409, "Prova değişmiş; kaydı yeniden yükleyin")
        return self.public(self.finish_record(record, "submitted"))

    def coach(self, exam_id: str, question_id: str, turn: int) -> dict:
        """Post-exam, source-bound deterministic coaching; unavailable during an exam."""
        record = self.get(exam_id)
        if record["state"] != "finished":
            raise HTTPException(409, "Koçluk yalnız deneme tamamlandıktan sonra açılır")
        if turn < 1 or turn > 3:
            raise HTTPException(422, "Koçluk turu 1 ile 3 arasında olmalı")
        task = next((item for item in self.tasks() if item["id"] == question_id), None)
        result = next((item for item in record.get("results") or [] if item["question_id"] == question_id), None)
        if task is None or result is None:
            raise HTTPException(404, "Soru bulunamadı")
        evidence = task.get("evidence", [])
        source_ids = [item["source_id"] for item in evidence]
        if result["correct"]:
            return {"stage": "correct_reflection", "turn": turn,
                    "text": "Yanıtın doğru. Kaynaktaki bilgiyle seçimini kendi cümlenle gerekçelendirebilir misin?",
                    "source_ids": source_ids, "can_reveal_explanation": True}
        if not evidence:
            return {"stage": "source_unavailable", "turn": turn,
                    "text": "Bu prova sorusu için öğretmen onaylı kaynak kanıtı yok; kaynaklı koçluk açılmadı.",
                    "source_ids": [], "can_reveal_explanation": False}
        first = evidence[0]["quote"]
        if turn == 1:
            text = "Soru kökünün senden istediği ilişkiyi kendi sözlerinle söyle. Hangi kavram belirleyici?"
        elif turn == 2:
            text = f"Kaynakta ‘{first}’ bilgisi var. Bu bilgi seçtiğin şıkla nasıl uyuşuyor ya da çelişiyor?"
        else:
            text = f"Kaynak açıklaması: {task['explanation']} Doğru seçeneğin neden daha uygun olduğunu kaynakla birlikte tekrar kur."
        return {"stage": "socratic" if turn < 3 else "explanation", "turn": turn,
                "text": text, "source_ids": source_ids, "can_reveal_explanation": turn == 3}

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
