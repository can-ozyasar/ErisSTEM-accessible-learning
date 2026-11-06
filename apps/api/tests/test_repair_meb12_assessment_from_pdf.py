from app.pipeline.repair_meb12_assessment_from_pdf import parse_page


def test_parse_layout_question_with_five_choices():
    parsed = parse_page(
        """
        13. Mustafa Kemal'in aldığı kararla ilgili aşağıdakilerden hangisi söylenemez?
        A) Birinci seçenek
        B) İkinci seçenek
        C) Üçüncü seçenek
        D) Dördüncü seçenek
        E) Beşinci seçenek
        14. Sonraki soru
        """
    )
    assert parsed[13]["stem"].startswith("Mustafa Kemal")
    assert [item["label"] for item in parsed[13]["choices"]] == list("ABCDE")
    assert 14 not in parsed


def test_parse_rejects_incomplete_choice_sequence():
    parsed = parse_page("10. Soru\nA) Bir\nB) İki\nC) Üç\nD) Dört\n")
    assert parsed == {}
