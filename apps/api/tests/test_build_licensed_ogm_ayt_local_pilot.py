import copy

import pytest

from app import exam_practice
from app.exam_practice import AytHistoryExamPack
from app.pipeline.build_licensed_ogm_ayt_local_pilot import build


QUESTION_CHECKSUM = "a" * 64
BOOK_CHECKSUM = "b" * 64


def _fixtures():
    candidate_id = "ogm-ayt-deneme:test:d1:p1:q1"
    questions = {
        "schema": "ayt-target-question-candidates-v1",
        "source_checksum": QUESTION_CHECKSUM,
        "rows": [{
            "candidate_id": candidate_id,
            "question": {
                "parts": [{"text": "İlk Çağ uygarlıklarından hangisi yazıyı kullanmıştır?"}],
                "choices": [
                    {"label": "A", "text": "Sümerler"},
                    {"label": "B", "text": "Hititler"},
                    {"label": "C", "text": "Frigler"},
                    {"label": "D", "text": "Lidyalılar"},
                    {"label": "E", "text": "Urartular"},
                ],
            },
        }],
    }
    answers = {"source_checksum": QUESTION_CHECKSUM, "records": [{"candidate_id": candidate_id, "correct_choice": "A"}]}
    evidence = {
        "source_checksum": QUESTION_CHECKSUM,
        "questions": [{
            "candidate_id": candidate_id,
            "evidence_bundle": [{
                "source_name": "meb-tarih-9.pdf",
                "source_checksum": BOOK_CHECKSUM,
                "page": 1,
                "bbox": [10, 10, 200, 100],
                "excerpt": "Sümerler, yazıyı kullanan İlk Çağ uygarlıklarından biridir.",
            }],
        }],
    }
    usage = {
        "source_checksum": QUESTION_CHECKSUM,
        "scope": "local_pilot_only",
        "local_pilot_confirmed": True,
        "student_publication_allowed": False,
    }
    sources = {
        "schema": "ayt-history-meb-source-catalog-v1",
        "sources": [{
            "id": "meb-tarih-9.pdf", "kind": "meb_textbook", "title": "MEB Tarih 9. Sınıf Ders Kitabı",
            "canonical_url": "https://tymm.meb.gov.tr/kitap/43/tarih-9.sinif-ders-kitabi",
            "source_checksum": BOOK_CHECKSUM, "relative_path": "meb-tarih-9.pdf", "page_count": 20,
        }],
    }
    return questions, answers, evidence, usage, sources


def test_builds_a_runtime_valid_local_only_pack():
    result = build(*_fixtures())

    parsed = AytHistoryExamPack.model_validate(result)
    assert parsed.content_mode == "licensed_local_pilot"
    assert len(parsed.questions) == 1
    assert parsed.questions[0].correct_label == "A"
    assert parsed.student_publication_allowed is False


def test_refuses_a_broken_checksum_chain():
    questions, answers, evidence, usage, sources = _fixtures()
    answers["source_checksum"] = "c" * 64

    with pytest.raises(ValueError, match="checksum zinciri"):
        build(questions, answers, evidence, usage, sources)


def test_refuses_publication_permission_claim():
    questions, answers, evidence, usage, sources = _fixtures()
    usage["student_publication_allowed"] = True

    with pytest.raises(ValueError, match="genel yayın"):
        build(questions, answers, evidence, usage, sources)


def test_refuses_evidence_that_is_not_in_the_meb_catalog():
    questions, answers, evidence, usage, sources = _fixtures()
    invalid_evidence = copy.deepcopy(evidence)
    invalid_evidence["questions"][0]["evidence_bundle"][0]["source_name"] = "bilinmeyen.pdf"

    with pytest.raises(ValueError, match="MEB kanıtı katalogla eşleşmiyor"):
        build(questions, answers, invalid_evidence, usage, sources)


def test_ai_bundle_without_final_verification_cannot_reach_coach(tmp_path, monkeypatch):
    import json

    pack = build(*_fixtures())
    pack["content_mode"] = "ai_source_reviewed_local_pilot"
    pack["questions"][0]["authorship"] = "ai_source_reviewed_local_pilot"
    pack["questions"][0]["review_method"] = "ai_source_consensus_pdf_review"
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setattr(exam_practice, "verify_pack_sources", lambda *_: None)
    exam_practice.active_tasks.cache_clear()
    try:
        tasks = exam_practice.active_tasks(str(path))
        assert len(tasks) == 1
        assert tasks[0]["evidence"] == []
    finally:
        exam_practice.active_tasks.cache_clear()
