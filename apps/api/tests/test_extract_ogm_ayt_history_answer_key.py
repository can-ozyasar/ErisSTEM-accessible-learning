
import pytest

from app.pipeline.extract_ogm_ayt_history_answer_key import parse_social_sciences_answers


def _page(answers):
    social = "\n".join(f"{number}. {answer}" for number, answer in enumerate(answers, 1))
    math = "\n".join(f"{number}. A" for number in range(1, 41))
    return f"TEST\n{social}\nMATEMATİK\n{math}"


def test_parse_first_40_answers_as_social_sciences():
    answers = list("ABCDE") * 8
    parsed = parse_social_sciences_answers(_page(answers))
    assert len(parsed) == 40
    assert parsed[25] == "E"
    assert parsed[40] == "E"


def test_parse_rejects_incomplete_or_out_of_order_answer_page():
    with pytest.raises(ValueError, match="iki adet"):
        parse_social_sciences_answers("1. A")
    broken = _page(list("ABCDE") * 8).replace("2. B", "3. B", 1)
    with pytest.raises(ValueError, match="sıralı"):
        parse_social_sciences_answers(broken)
