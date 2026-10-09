"""Procedural practice with sourced annual arrangements, not official exam questions."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .learning_operations import LearningOperationsStore, StrictInput

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
                                    "bank_checksum": BANK_CHECKSUM, "state": "active",
                                    "answers": {}, "flags": {}, "results": None}, 0)
        return self.public(record)

    def get(self, exam_id: str):
        record = self.records.get(exam_id)
        if record is None or "bank_checksum" not in record:
            raise HTTPException(404, "Prova bulunamadı")
        if record["bank_checksum"] != BANK_CHECKSUM:
            raise HTTPException(409, "Soru bankası değişmiş; yeni prova başlatın")
        if record["state"] == "active" and self.now() >= record["deadline"]:
            return self.finish_record(record, "time_expired")
        return record

    def public(self, record: dict):
        return {**record,
                "questions": [{"id": task["id"], "question": task["question"],
                               "choices": [{"id": f"option-{i+1}", "text": text} for i, text in enumerate(task["choices"])]}
                              for task in TASKS],
                "server_now": self.now(),
                "notice": "Altı sentetik soruyla süre, okuyucu ve yanıt gezinmesi provasıdır. Resmî soru, tam müfredat denemesi veya gerçek sınavın birebir karşılığı değildir. 2026 profilleri sonraki yıllara uygulanmaz."}

    def answer(self, exam_id: str, request: ExamAnswer):
        record = self.get(exam_id)
        if record["state"] != "active":
            raise HTTPException(409, "Prova bitmiş; yanıt değiştirilemez")
        task = next((item for item in TASKS if item["id"] == request.question_id), None)
        if task is None:
            raise HTTPException(404, "Soru bulunamadı")
        if request.answer is not None and request.answer not in {f"option-{i+1}" for i in range(len(task["choices"]))}:
            raise HTTPException(422, "Geçerli bir seçenek seçin")
        return self.public(self.records.save(exam_id, "exam", "exam-procedure",
                          {**record, "answers": {**record["answers"], request.question_id: request.answer},
                           "flags": {**record["flags"], request.question_id: request.flagged}}, request.revision))

    def finish_record(self, record: dict, reason: str):
        results = []
        for task in TASKS:
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
                    if record["bank_checksum"] == BANK_CHECKSUM:
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
