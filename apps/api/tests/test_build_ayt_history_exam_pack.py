import hashlib
import json

import pytest

from app.pipeline.build_ayt_history_exam_pack import build


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _fixtures():
    questions = []
    records = []
    reviews = []
    for number in range(120):
        identifier = f"authoring-{number:03d}"
        split = "development" if number < 72 else "retrieval_test" if number < 96 else "system_acceptance"
        question = {"id": identifier, "authorship": "original", "status": "source_crop_validation_required",
                    "question": f"Özgün tarih sorusu {number} hangi bilgiyi ölçer?", "spoken_question": f"Özgün tarih sorusu {number} hangi bilgiyi ölçer?",
                    "choices": [f"Seçenek {letter}" for letter in "ABCDE"], "correct_label": "A",
                    "explanation": "MEB kaynağına dayalı kısa açıklama öğrencinin gerekçesini düzeltir.",
                    "source_evidence": {"source_id": "meb-tarih-9", "source_checksum": "a" * 64,
                                        "page": 1, "bbox": [1, 1, 2, 2], "quote": "Kaynakta doğrulanmış kısa kanıt bulunur.",
                                        "section_title": "Tarih Bilimi"}}
        questions.append(question)
        records.append({"id": identifier, "split": split})
        reviews.append({"id": identifier, "status": "human_approved", "reviewer": "Yerel içerik incelemesi",
                        "question_checksum": _digest(question), "checks": {key: True for key in (
                            "question_choices_match", "correct_label_grounded", "explanation_grounded",
                            "spoken_text_checked", "text_only_accessible")}})
    candidate = {"schema": "ayt-history-original-question-candidate-pack-v1", "candidate_checksum": "c" * 64, "questions": questions}
    sources = {"schema": "ayt-history-meb-source-catalog-v1", "sources": [{"id": "meb-tarih-9", "kind": "meb_textbook", "title": "MEB Tarih 9", "canonical_url": "https://meb.gov.tr/tarih.pdf", "source_checksum": "a" * 64, "relative_path": "tarih.pdf", "page_count": 10}]}
    split = {"schema": "ayt-history-candidate-split-v1", "records": records}
    review = {"schema": "ayt-history-human-pdf-crop-review-template-v1", "candidate_checksum": "c" * 64,
              "question_set_checksum": _digest(questions), "reviews": reviews}
    return candidate, sources, split, review


def test_builds_only_completely_human_reviewed_pack():
    result = build(*_fixtures(), pack_id="ayt-local-v1")
    assert result["schema"] == "ayt-history-exam-pack-v1"
    assert len(result["questions"]) == 120
    assert result["questions"][0]["review_method"] == "human_pdf_crop_review"
    assert result["runtime_enabled"] is False


def test_rejects_incomplete_human_review():
    candidate, sources, split, review = _fixtures()
    review["reviews"][12]["checks"]["spoken_text_checked"] = None
    with pytest.raises(ValueError, match="onayı eksik"):
        build(candidate, sources, split, review, pack_id="ayt-local-v1")
