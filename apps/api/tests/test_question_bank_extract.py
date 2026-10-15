from pathlib import Path
import re

import pymupdf
import pytest

from app.question_bank_extract import Line, _answer_key_lines, extract_book, extract_page
from app.question_bank_structure import Question, navigation_units
from app.question_bank_visual_proposals import SOURCE_CHECKSUM


BOOK = Path(__file__).parents[3] / "data/soru_bankasi/vip-9-sinif-tarih-soru-bankasi.pdf"
pytestmark = pytest.mark.skipif(not BOOK.is_file(), reason="Local copyrighted source not installed")


def test_real_page_10_separates_question_visual_blanks_and_choices():
    with pymupdf.open(BOOK) as pdf:
        items = extract_page(pdf[9], 10, "a" * 64)
    by_number = {item["question"]["number"]: item for item in items}
    assert set(by_number) == {7, 8, 9, 10, 11, 12}
    assert len(by_number[7]["question"]["visuals"]) == 1
    assert "visual_description_required" in by_number[7]["issues"]
    assert sum(len(part["blanks"]) for part in by_number[8]["question"]["parts"]) == 2
    assert [choice["label"] for choice in by_number[10]["question"]["choices"]] == list("ABCDE")
    assert by_number[10]["issues"] == []


def test_two_column_page_reads_left_column_before_right_column():
    with pymupdf.open(BOOK) as pdf:
        items = extract_page(pdf[4], 5, "a" * 64)
    assert [item["question"]["number"] for item in items] == [1, 2, 3, 4, 5, 6]


def test_real_open_response_page_is_not_treated_as_broken_mcq():
    with pymupdf.open(BOOK) as pdf:
        items = extract_page(pdf[20], 21, "a" * 64)
    assert len(items) == 6
    assert all(item["question"]["question_type"] != "multiple_choice" for item in items)
    assert all("choices_incomplete_or_out_of_order" not in item["issues"] for item in items)


def test_map_question_choice_table_keeps_roman_column_meaning():
    with pymupdf.open(BOOK) as pdf:
        first = extract_page(pdf[28], 29, "a" * 64)[0]
    assert first["question"]["number"] == 1
    assert first["question"]["choices"][0]["text"] == "I: İbraniler; II: Asurlular; III: Urartular"
    assert "choice_table_review_required" in first["issues"]
    units = navigation_units(Question.model_validate(first["question"]))
    assert "Birinci sütun: İbraniler" in next(unit["spoken_text"] for unit in units if unit["label"] == "Şık A")


def test_horizontal_choice_cells_do_not_flatten_into_one_phrase():
    with pymupdf.open(BOOK) as pdf:
        item = next(item for item in extract_page(pdf[4], 5, "a" * 64)
                    if item["question"]["number"] == 3)
    assert "horizontal_choice_cells_review_required" in item["issues"]
    assert "Birinci sütun:" in item["question"]["choices"][0]["text"]
    assert "Üçüncü sütun:" in item["question"]["choices"][0]["text"]


def test_two_pictures_have_left_to_right_roman_labels():
    with pymupdf.open(BOOK) as pdf:
        item = next(item for item in extract_page(pdf[45], 46, "a" * 64)
                    if item["question"]["number"] == 7)
    visuals = item["question"]["visuals"]
    assert [visual["label"] for visual in visuals] == ["I", "II"]
    assert visuals[0]["source"]["bbox"][0] < visuals[1]["source"]["bbox"][0]


def test_source_bound_visual_drafts_never_count_as_reviewed():
    with pymupdf.open(BOOK) as pdf:
        item = next(item for item in extract_page(pdf[28], 29, SOURCE_CHECKSUM)
                    if item["question"]["number"] == 1)
    visual = item["question"]["visuals"][0]
    assert visual["kind"] == "map"
    assert "I, Doğu Akdeniz" in visual["description"]
    assert visual["description_reviewed"] is False
    with pytest.raises(ValueError):
        Question.model_validate({**item["question"], "status": "approved"})


def test_visual_draft_is_not_reused_for_other_pdf_checksum():
    with pymupdf.open(BOOK) as pdf:
        item = next(item for item in extract_page(pdf[28], 29, "a" * 64)
                    if item["question"]["number"] == 1)
    assert item["question"]["visuals"][0]["description"] is None


def test_all_pages_separate_question_text_from_page_furniture_and_answer_key():
    book = extract_book(BOOK)
    assert len(book["questions"]) == 306
    for item in book["questions"]:
        question = item["question"]
        text = " ".join([*(part["text"] for part in question["parts"]),
                         *(choice["text"] for choice in question["choices"])])
        assert "TARİH SORU BANKASI" not in text, question["id"]
        assert "9. SINIF" not in text, question["id"]
        assert not re.search(r"\b\d{1,2}\s*[-–]\s*[A-E]\b", text), question["id"]
    contexts = book["page_contexts"]
    assert contexts[3]["topic"] == "Tarih Öğrenmenin Faydaları, Tarihin Doğası"
    assert (contexts[3]["test_name"], contexts[3]["test_number"]) == ("Kavrama Testi", 1)
    assert (contexts[5]["test_name"], contexts[5]["test_number"]) == ("Kavrama Testi", 2)
    assert (contexts[9]["test_name"], contexts[9]["test_number"]) == ("VIP Testi", 4)
    assert contexts[15]["topic"] == "Tarihsel Bilginin Üretim Süreci, Yardımcı Bilimler, Dijital Dönüşüm"
    assert contexts[21]["test_name"] == "Alıştırmalar"
    assert (contexts[29]["test_name"], contexts[29]["test_number"]) == ("Kavrama Testi", 4)


def test_answer_key_detection_uses_repeated_cells_in_a_margin():
    cells = [Line(f"{number}-{letter}", (80 + index * 40, 735, 110 + index * 40, 747), False)
             for index, (number, letter) in enumerate([(1, "C"), (2, "A"), (3, "D"), (4, "E")])]
    isolated = Line("1-A", (80, 300, 110, 312), False)
    assert _answer_key_lines([isolated, *cells], 800) == {1, 2, 3, 4}
