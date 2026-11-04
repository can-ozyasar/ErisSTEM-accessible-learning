from app.pipeline.ogm_ayt_transcribe import _transcribe


def test_transcription_uses_layout_boundaries_and_never_adds_answer_fields():
    labels = [{"label": label, "left": 10 + index * 80, "top": 100, "width": 12, "height": 12}
              for index, label in enumerate("ABCDE")]
    candidate = {"candidate_id": "q1", "topic": "Konu", "page": 1,
                 "layout": {"column": 0, "option_label_boxes": labels}}
    words = ([{"text": "Kök", "left": 10, "top": 95, "width": 20, "height": 10}]
             + [{"text": f"seçenek{index}", "left": 25 + index * 80, "top": 100, "width": 30, "height": 10}
                for index in range(5)])
    row = _transcribe(candidate, [candidate], 1000, 300, words)
    assert row["transcription_status"] == "private_teacher_review_required"
    assert [choice["label"] for choice in row["question"]["choices"]] == list("ABCDE")
    assert "answer" not in row["question"]
