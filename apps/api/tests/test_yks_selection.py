from app.yks_selection import ExamTag, rank_scope


def tag(identifier, grade, unit, *, direct=True, accessible=True, relation="neden_oldu"):
    return ExamTag(identifier, 2025, "AYT", 1, grade, unit, "kavram", relation, False, direct, accessible, "Öğretmen", True)


def test_scope_ranking_uses_only_reviewed_metadata_and_is_explainable():
    tags = [tag(f"g10-{index}", 10, f"10.{index % 6}") for index in range(12)]
    tags += [tag(f"g9-{index}", 9, "9.1", direct=False, accessible=False) for index in range(3)]
    result = rank_scope(tags)
    assert result["chosen_grade"] == 10
    assert len(result["selected_units"]) == 6
    assert result["weights"]["frequency"] == .40
