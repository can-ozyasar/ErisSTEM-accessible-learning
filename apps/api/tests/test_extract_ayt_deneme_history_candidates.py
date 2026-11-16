from pathlib import Path

import pymupdf
import pytest

from app.pipeline.extract_ayt_deneme_history_candidates import (
    _is_history_one_page,
    _repair_inline_choice_boxes,
    _section_options,
    build,
)
from app.question_bank_extract import extract_page
from app.question_scope import visual_dependency_reasons


@pytest.fixture
def supplementary_deneme_pdf():
    source = Path("data/private/ogm-supplementary-v1/tum-dersler-deneme.pdf")
    if not source.exists():
        pytest.skip("Private supplementary exam PDF is not available in this checkout")
    return source


def test_section_hints_are_candidates_not_answer_labels():
    assert "1.3" in _section_options("Mondros Ateşkes Antlaşması sonrasında Osmanlı Devleti")
    assert "2.5" in _section_options("Sakarya ve Batı Cephesi")
    assert "2.4" in _section_options("Kâzım Karabekir ve Gümrü Antlaşması")
    assert "3.2" in _section_options("Saltanatın kaldırılması ve Cumhuriyetin ilanı")
    assert "3.1" in _section_options("Laiklik ve devletçilik ilkeleri")
    assert _section_options("Osmanlı meclisi ve eğitim faaliyetleri") == []
    assert _section_options("Coğrafi nüfus dağılımı") == []
    assert "1.3" not in _section_options("II. Dünya Savaşı sonrası gelişmeler")
    assert "1.3" in _section_options("I. Dünya Savaşı sonrası gelişmeler")


def test_extracts_only_clean_history_questions_from_selected_deneme(
    tmp_path: Path, supplementary_deneme_pdf: Path
):
    source = supplementary_deneme_pdf
    result = build(source, denemeler={1})
    assert result["selected_denemeler"] == [1]
    assert result["candidate_count"] > 0
    assert result["review_count"] == len(result["review_queue"])
    assert all(row["status"] == "private_pdf_crop_review_required"
               for row in result["review_queue"])
    assert all(25 <= row["question"]["number"] <= 34 for row in result["rows"])
    assert all(row["answer_key_accessed"] is False for row in result["rows"])
    assert all(row["worked_explanation_accessed"] is False for row in result["rows"])
    assert all(row["target_section_status"] in {
        "lexical_candidate_requires_review", "unresolved_section_requires_review"
    } for row in result["rows"])
    assert all(row["printed_test"] == "AYT_TDE_SOSYAL_1" for row in result["rows"])
    assert {28, 29}.issubset({row["question"]["number"] for row in result["rows"]})


def test_question_number_cannot_override_printed_test_heading(supplementary_deneme_pdf: Path):
    source = supplementary_deneme_pdf
    with pymupdf.open(source) as pdf:
        assert _is_history_one_page(pdf[22]) is True
        assert _is_history_one_page(pdf[334]) is False


def test_inline_ayt_options_are_separated_but_still_need_pdf_review(
    supplementary_deneme_pdf: Path,
):
    source = supplementary_deneme_pdf
    with pymupdf.open(source) as pdf:
        item = next(row for row in extract_page(pdf[77], 78, "a" * 64)
                    if row["question"]["number"] == 31)
        assert item["question"]["source"]["bbox"][2] <= pdf[77].rect.width / 2
    assert [choice["label"] for choice in item["question"]["choices"]] == list("ABCDE")
    assert [choice["text"] for choice in item["question"]["choices"][:3]] == [
        "Yalnız I", "Yalnız II", "Yalnız III",
    ]
    assert "inline_choice_layout_review_required" in item["issues"]


def test_pdf_word_geometry_repairs_only_exact_inline_choice_text(supplementary_deneme_pdf: Path):
    source = supplementary_deneme_pdf
    with pymupdf.open(source) as pdf:
        item = next(row for row in extract_page(pdf[77], 78, "a" * 64)
                    if row["question"]["number"] == 31)
        repaired = _repair_inline_choice_boxes(item["question"], pdf[77].get_text("words"))
    assert repaired is not None
    boxes = [tuple(choice["source"]["bbox"]) for choice in repaired["choices"]]
    assert len(set(boxes)) == 5
    assert boxes[0][2] < boxes[1][0] < boxes[2][0]
    altered = item["question"].copy()
    altered["choices"] = [*item["question"]["choices"]]
    altered["choices"][0] = {**altered["choices"][0], "text": "Yanlış metin"}
    with pymupdf.open(source) as pdf:
        assert _repair_inline_choice_boxes(altered, pdf[77].get_text("words")) is None


def test_vector_drawn_diagram_question_is_excluded_from_text_scope(
    supplementary_deneme_pdf: Path,
):
    source = supplementary_deneme_pdf
    with pymupdf.open(source) as pdf:
        item = next(row for row in extract_page(pdf[375], 376, "a" * 64)
                    if row["question"]["number"] == 33)
    assert "referenced_visual" in visual_dependency_reasons(item["question"], item["issues"])
