from app.pipeline.ogm_ayt_layout_candidates import _balanced_rows, _groups


def test_groups_accepts_two_column_complete_a_to_e_sequences():
    rows = []
    for column, left in ((0, 10), (1, 510)):
        for offset, label in enumerate("ABCDE"):
            rows.append({"text": f"{label})", "left": str(left + offset), "top": str(100 + offset), "width": "8", "height": "8"})
    groups = _groups(rows, 1000)
    assert [(group["column"], group["ordinal"]) for group in groups] == [(0, 1), (1, 1)]


def test_groups_rejects_a_partial_sequence():
    rows = [{"text": f"{label})", "left": "10", "top": str(index), "width": "8", "height": "8"}
            for index, label in enumerate("ABCD")]
    assert _groups(rows, 1000) == []


def test_balanced_rows_cycles_across_pages():
    rows = [{"page": 1, "candidate_id": "a"}, {"page": 1, "candidate_id": "b"},
            {"page": 2, "candidate_id": "c"}, {"page": 2, "candidate_id": "d"}]
    assert [row["candidate_id"] for row in _balanced_rows(rows, 3)] == ["a", "c", "b"]
