import json

from app.pipeline.ayt_evidence_review_pack import build


def test_empty_suggestions_create_private_review_shell_and_escape_question(tmp_path):
    questions = {
        "schema": "ayt-tarih2-candidates-v1", "source_checksum": "question-v1",
        "candidates": [{
            "candidate_id": "q1", "question": {"parts": [{"text": "<metin>"}], "choices": []},
        }],
    }
    proposals = {
        "schema": "ayt-evidence-proposals-v1", "question_source_checksum": "question-v1",
        "corpus_checksum": "corpus-v1",
        "proposals": [{"candidate_id": "q1", "exam_year": 2024,
                       "status": "teacher_review_required", "suggestions": []}],
    }
    result = build(questions, proposals, tmp_path, tmp_path / "pack")
    assert result["review_count"] == 1
    assert result["crop_count"] == 0
    assert json.loads((tmp_path / "pack" / "manifest.json").read_text())["corpus_checksum"] == "corpus-v1"
    assert "&lt;metin&gt;" in (tmp_path / "pack" / "index.html").read_text()
