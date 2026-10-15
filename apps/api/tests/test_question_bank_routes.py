from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.job_store import make_session_factory
from app.learning_operations import LearningOperationsStore
from app import question_bank_routes


BOOK = Path(__file__).parents[3] / "data/soru_bankasi/vip-9-sinif-tarih-soru-bankasi.pdf"
pytestmark = pytest.mark.skipif(not BOOK.is_file(), reason="Local copyrighted source not installed")


def test_teacher_review_controls_student_release(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(question_bank_routes, "SOURCE", BOOK)
    store = LearningOperationsStore(make_session_factory(f"sqlite:///{tmp_path / 'review.db'}"))
    app = FastAPI()
    app.include_router(question_bank_routes.question_bank_router(store))
    client = TestClient(app)
    teacher = {"X-Role": "teacher"}
    student = {"X-Role": "student"}
    base = "/v1/question-bank"

    assert client.get(f"{base}/student/questions", headers=student).json() == []
    page = client.get(f"{base}/teacher/pages/10", headers=teacher).json()
    q7 = next(item for item in page["questions"] if item["question"]["number"] == 7)
    visual = {**q7["question"], "status": "approved"}
    denied = client.put(f"{base}/teacher/questions/{visual['id']}", headers=teacher,
                        json={"question": visual, "expected_revision": 0, "reason": "Kaynak karşılaştırıldı"})
    assert denied.status_code == 422
    without_visual = {**q7["question"], "visuals": [], "status": "approved"}
    deleted = client.put(f"{base}/teacher/questions/{visual['id']}", headers=teacher,
                         json={"question": without_visual, "expected_revision": 0,
                               "reason": "Görsel denetimini atlama girişimi"})
    assert deleted.status_code == 422

    q10 = next(item for item in page["questions"] if item["question"]["number"] == 10)
    approved = {**q10["question"], "status": "approved"}
    saved = client.put(f"{base}/teacher/questions/{approved['id']}", headers=teacher,
                       json={"question": approved, "expected_revision": 0,
                             "reason": "PDF metni ve seçenekler karşılaştırıldı"})
    assert saved.status_code == 200, saved.text
    listing = client.get(f"{base}/student/questions", headers=student).json()
    assert [item["id"] for item in listing] == [approved["id"]]
    assert listing[0]["context"]["topic"] == "Tarih Öğrenmenin Faydaları, Tarihin Doğası"
    assert listing[0]["context"]["test_name"] == "VIP Testi"
    reading = client.get(f"{base}/student/questions/{approved['id']}", headers=student).json()
    assert [unit["label"] for unit in reading["units"]][-5:] == ["Şık A", "Şık B", "Şık C", "Şık D", "Şık E"]
    with_answer_key = {**approved, "parts": [
        {**approved["parts"][0], "text": approved["parts"][0]["text"] + " 1-C 2-A 3-D"},
        *approved["parts"][1:],
    ]}
    assert client.put(f"{base}/teacher/questions/{approved['id']}", headers=teacher,
                      json={"question": with_answer_key, "expected_revision": 1,
                            "reason": "Cevap anahtarı karışmış kaynak"}).status_code == 422

    page9 = client.get(f"{base}/teacher/pages/9", headers=teacher).json()
    clean_ids = [item["question"]["id"] for item in page9["questions"] if not item["issues"]]
    denied_batch = client.post(f"{base}/teacher/pages/9/approve-clean", headers=teacher,
                               json={"question_ids": clean_ids, "source_checked": True,
                                     "choices_checked": False, "reading_order_checked": True,
                                     "reason": "Tam sayfa kaynakla karşılaştırıldı"})
    assert denied_batch.status_code == 422
    approved_batch = client.post(f"{base}/teacher/pages/9/approve-clean", headers=teacher,
                                 json={"question_ids": clean_ids, "source_checked": True,
                                       "choices_checked": True, "reading_order_checked": True,
                                       "reason": "Tam sayfa kaynak ve okuma sırası karşılaştırıldı"})
    assert approved_batch.status_code == 200, approved_batch.text
    assert approved_batch.json()["approved_count"] == len(clean_ids)

    contaminated = {**approved, "parts": [
        {**approved["parts"][0], "text": approved["parts"][0]["text"] + " TARİH SORU BANKASI"},
        *approved["parts"][1:],
    ]}
    checksum = listing[0]["context"]["source"]["source_checksum"]
    store.save(question_bank_routes._record_id(checksum, approved["id"]), "qb", checksum[:16],
               {"question": contaminated, "reason": "Eski onaylı kayıttaki sayfa süsü"}, 1)
    updated = client.get(f"{base}/student/questions", headers=student).json()
    assert approved["id"] not in [item["id"] for item in updated]
    assert client.get(f"{base}/student/questions/{approved['id']}", headers=student).status_code == 404
    recheck = client.get(f"{base}/teacher/pages/10", headers=teacher).json()
    flagged = next(item for item in recheck["questions"] if item["question"]["id"] == approved["id"])
    assert "approved_page_furniture_review_required" in flagged["issues"]
    assert "TARİH SORU BANKASI" not in str(flagged["source_candidate"])
