from copy import deepcopy

from app.pipeline.validate_ayt_history_retrieval_pdf_review import validate


def _template():
    rows = []
    for number in range(24):
        rows.append({"id": f"q-{number}", "question": "Soru", "choices": ["A", "B", "C", "D", "E"], "cards": [
            {"source_key": f"a-{number}-{card}", "source_checksum": "source", "atom_id": str(card), "page": 1,
             "bbox": [1, 2, 3, 4], "crop": "crop.png", "excerpt": "Kaynak", "decision": None, "rationale": ""}
            for card in range(3)]})
    return {"schema": "ayt-history-rank-blind-pdf-retrieval-review-template-v1", "candidate_checksum": "a",
            "corpus_checksum": "b", "split_checksum": "c", "source_catalog_checksum": "d", "reviews": rows,
            "answer_key_accessed": False, "worked_explanation_accessed": False, "reference_atom_accessed": False,
            "runtime_enabled": False, "qlora_enabled": False}


def _completed():
    result = deepcopy(_template())
    for row in result["reviews"]:
        row.update(reviewer="manual-reviewer", reviewed_at="2026-11-21T10:30:00+03:00", case_decision="sufficient")
        for number, card in enumerate(row["cards"]):
            card["decision"] = "relevant" if number == 0 else "wrong"
            card["rationale"] = "PDF kesiti sorudaki ilişkiyi açıkça gösteriyor."
    return result


def test_validates_complete_bound_rank_blind_review():
    result = validate(_template(), _completed())
    assert result["review_count"] == 24
    assert result["summary"]["case_decisions"] == {"sufficient": 24}
    assert result["runtime_enabled"] is False


def test_rejects_changed_provenance_or_invalid_sufficiency():
    completed = _completed()
    completed["reviews"][0]["cards"][0]["excerpt"] = "Değiştirildi"
    try:
        validate(_template(), completed)
    except ValueError as error:
        assert "değiştirilemez" in str(error)
    else:
        raise AssertionError("Provenance değişikliği reddedilmeliydi")
    completed = _completed()
    completed["reviews"][0]["case_decision"] = "insufficient"
    try:
        validate(_template(), completed)
    except ValueError as error:
        assert "insufficient" in str(error)
    else:
        raise AssertionError("Relevant kartlı insufficient vaka reddedilmeliydi")
