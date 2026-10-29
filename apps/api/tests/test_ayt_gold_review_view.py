import json

from app.pipeline.ayt_gold_review_view import build


def test_gold_review_view_is_answer_free_and_binds_crop_metadata(tmp_path):
    manifest = {
        "schema": "ayt-evidence-review-pack-v1", "corpus_checksum": "corpus-v1",
        "question_source_checksum": "questions-v1", "reviews": [{
            "candidate_id": "q1", "exam_year": 2024, "question_text": "<soru>", "cards": [{
                "source_name": "history.pdf", "grade": 9, "page": 12, "section_title": "Tarih",
                "crop": "crops/a.png", "source_checksum": "book-v1", "chunk_id": "chunk-v1",
            }],
        }],
    }
    target = tmp_path / "review.html"
    build(manifest, target)
    text = target.read_text(encoding="utf-8")
    assert "&lt;soru&gt;" in text
    assert "answer_label" not in text
    assert "ayt-retrieval-gold-v1" in text
    assert "chunk-v1" in text
    json.dumps(manifest)
