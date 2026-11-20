from app.pipeline.build_original_question_candidate_pack import build


def gate(prefix: int):
    rows = []
    for number, label in enumerate("ABCDE" * 24, start=prefix):
        rows.append({"draft": {"id": f"authoring-{number:03d}", "question": "Metin sorusu", "choices": ["a", "b", "c", "d", "e"],
                      "correct_label": label, "source_evidence": {"grade": 9 + number % 4, "section_id": str(number % 7)}},
                     "independent_review": {"verdict": "accept_for_source_validation"},
                     "source_crop_validation_required": True, "runtime_enabled": False})
    return {"schema": "ayt-history-original-question-review-gate-v1", "corpus_checksum": "c", "accepted_for_source_crop_validation": rows}


def test_selects_120_with_balanced_correct_option_positions():
    result = build([gate(1)])
    assert result["summary"]["question_count"] == 120
    assert result["summary"]["answer_label_distribution"] == {label: 24 for label in "ABCDE"}
    assert result["runtime_enabled"] is False


def test_replaces_an_excluded_question_with_another_same_label_candidate():
    extra = gate(1)
    extra["accepted_for_source_crop_validation"].append({"draft": {"id": "authoring-121", "question": "Metin sorusu", "choices": ["a", "b", "c", "d", "e"],
        "correct_label": "A", "source_evidence": {"grade": 12, "section_id": "extra"}}, "independent_review": {"verdict": "accept_for_source_validation"},
        "source_crop_validation_required": True, "runtime_enabled": False})
    result = build([extra], exclude_ids={"authoring-001"})
    assert "authoring-001" not in {row["id"] for row in result["questions"]}
    assert result["summary"]["answer_label_distribution"]["A"] == 24
