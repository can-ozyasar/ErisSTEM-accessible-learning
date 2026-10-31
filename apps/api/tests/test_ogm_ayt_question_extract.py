from app.pipeline.ogm_ayt_question_extract import extract_page


def test_extracts_only_complete_answer_free_multiple_choice_blocks():
    text = "1. Kök metni\nA) Bir\nB) İki\nC) Üç\nD) Dört\nE) Beş\n2. Çözüm: gizli"
    rows, rejected = extract_page(text)
    assert len(rows) == 1
    assert [choice["label"] for choice in rows[0]["choices"]] == list("ABCDE")
    assert rejected["solution_or_answer_marker"] == 1


def test_rejects_partial_choice_sequences():
    rows, rejected = extract_page("1. Kök\nA) Bir\nB) İki\nC) Üç")
    assert rows == []
    assert rejected["incomplete_or_unordered_choices"] == 1
