"""PDF scope review may open discovery, never production or answer access."""

import pytest

from app.pipeline.project_reviewed_deneme_scope import build


def _payloads():
    question_checksum = "q" * 64
    pool = {"schema": "ayt-target-question-candidates-v1",
            "source_checksum": question_checksum,
            "answer_key_accessed": False, "worked_explanation_accessed": False,
            "rows": [{"candidate_id": "q1", "source_kind": "private_deneme",
                      "source_checksum": question_checksum, "page": 1,
                      "question": {"source": {"source_checksum": question_checksum,
                                              "bbox": [1, 2, 3, 4]},
                                   "parts": [{"text": "Amasya Genelgesi hakkında hangisi?"}],
                                   "choices": [{"label": letter, "text": letter}
                                               for letter in "ABCDE"]}}]}
    teacher = {"schema": "ayt-deneme-scope-teacher-review-v1",
               "source_pdf_checksum": question_checksum,
               "reviewer_role": "independent_history_teacher_agent",
               "answer_key_accessed": False, "worked_solution_accessed": False,
               "rows": [{"candidate_id": "q1", "teacher_scope_decision": "in_scope_text_question",
                         "teacher_section_id": "2.1", "pdf_crop_checked": True,
                         "pdf_crop_bbox": [1, 2, 3, 4],
                         "stem_and_five_choices_pdf_checked": True,
                         "choice_count": 5, "visual_dependency": "none_detected_in_question_crop",
                         "transcription_verdict": "text_and_choices_match_pdf_crop", "flags": []}]}
    scope = {"source_binding": {"corpus_checksum": "c" * 64},
             "sections": [{"section_id": section_id}
                          for section_id in ("1.3", "2.1", "2.4", "2.5", "3.1", "3.2")]}
    return pool, teacher, scope


def test_projection_preserves_teacher_scope_without_approving_evidence():
    pool, teacher, scope = _payloads()
    result = build(pool, teacher, scope)
    assert result["candidate_count"] == 1
    assert result["rows"][0]["target_section_options"] == ["2.1"]
    assert result["rows"][0]["question"]["stem"].startswith("Amasya")
    assert result["runtime_enabled"] is False and result["qlora_enabled"] is False
    assert result["answer_key_accessed"] is False


def test_projection_rejects_unchecked_crop_and_wrong_source():
    pool, teacher, scope = _payloads()
    teacher["rows"][0]["pdf_crop_checked"] = False
    with pytest.raises(ValueError, match="PDF"):
        build(pool, teacher, scope)
    teacher["rows"][0]["pdf_crop_checked"] = True
    pool["rows"][0]["question"]["source"]["source_checksum"] = "x" * 64
    with pytest.raises(ValueError, match="kaynak izi"):
        build(pool, teacher, scope)


def test_projection_checks_each_repaired_choice_box():
    pool, teacher, scope = _payloads()
    teacher["schema"] = "ayt-deneme-inline-repair-teacher-review-v1"
    teacher["all_choice_boxes_match_pdf"] = True
    review = teacher["rows"][0]
    review.update({"question_pdf_crop_visually_checked": True,
                   "stem_and_statement_text_pdf_checked": True,
                   "question_bbox": [1, 2, 3, 4],
                   "layout_repair_method": "pdf_word_geometry_exact_choice_match_v1",
                   "choice_geometry_checks": [
                       {"label": choice["label"], "pdf_text_match": True,
                        "box_inside_question": True, "bbox": [1, 2, 3, 4]}
                       for choice in pool["rows"][0]["question"]["choices"]]})
    pool["rows"][0]["layout_repair"] = "pdf_word_geometry_exact_choice_match_v1"
    for choice in pool["rows"][0]["question"]["choices"]:
        choice["source"] = {"bbox": [1, 2, 3, 4]}
    assert build(pool, teacher, scope)["candidate_count"] == 1
    review["choice_geometry_checks"][1]["bbox"] = [2, 2, 3, 4]
    with pytest.raises(ValueError, match="koordinatı"):
        build(pool, teacher, scope)


def test_projection_checks_remaining_question_parts_and_duplicate_reviews():
    pool, teacher, scope = _payloads()
    teacher["schema"] = "ayt-deneme-remaining-scope-teacher-review-v1"
    teacher["all_choice_boxes_match_pdf"] = True
    teacher["all_question_parts_match_pdf"] = True
    review = teacher["rows"][0]
    review.update({"question_pdf_crop_visually_checked": True,
                   "stem_and_statement_text_pdf_checked": True,
                   "question_bbox": [1, 2, 3, 4],
                   "part_geometry_checks": [{"pdf_text_match": True, "bbox": [1, 2, 3, 4]}],
                   "choice_geometry_checks": [
                       {"label": letter, "pdf_text_match": True,
                        "box_inside_question": True, "bbox": [1, 2, 3, 4]}
                       for letter in "ABCDE"]})
    pool["rows"][0]["question"]["parts"][0]["source"] = {"bbox": [1, 2, 3, 4]}
    for choice in pool["rows"][0]["question"]["choices"]:
        choice["source"] = {"bbox": [1, 2, 3, 4]}
    assert build(pool, teacher, scope)["candidate_count"] == 1
    with pytest.raises(ValueError, match="Yinelenen öğretmen"):
        build(pool, [teacher, teacher], scope)
    review["part_geometry_checks"][0]["bbox"] = [2, 2, 3, 4]
    with pytest.raises(ValueError, match="Soru kökü koordinatı"):
        build(pool, teacher, scope)
