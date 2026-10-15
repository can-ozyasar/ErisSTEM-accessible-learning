import pymupdf

from app.history_source import _join_lines, _kind, _text_regions


def test_soft_hyphen_and_question_classification():
    assert _join_lines(["harita\xad", "sı incelendi."]) == "haritası incelendi."
    assert _kind("Kaynak Ç") == "source_label"
    assert _kind("1. Harita ne gösterir?") == "question_or_instruction"


def test_numbered_questions_become_individual_regions():
    pdf = pymupdf.open()
    page = pdf.new_page(width=550, height=780)
    page.insert_text((50, 110), "1. Ilk soru nedir?\n2. Ikinci soru nedir?", fontsize=12)
    regions = _text_regions(page)
    assert len(regions) == 2
    assert all(region["kind"] == "question_or_instruction" for region in regions)
