from pathlib import Path

from app.pipeline.extract_ayt_deneme_history_candidates import _section_options, build


def test_section_hints_are_candidates_not_answer_labels():
    assert "1.3" in _section_options("Mondros sonrasında Osmanlı Devleti")
    assert "2.4" in _section_options("Sakarya ve Batı Cephesi")
    assert _section_options("Coğrafi nüfus dağılımı") == []


def test_extracts_only_clean_history_questions_from_selected_deneme(tmp_path: Path):
    source = Path("data/private/ogm-supplementary-v1/tum-dersler-deneme.pdf")
    result = build(source, denemeler={1})
    assert result["selected_denemeler"] == [1]
    assert result["candidate_count"] > 0
    assert all(25 <= row["question"]["number"] <= 34 for row in result["rows"])
    assert all(row["answer_key_accessed"] is False for row in result["rows"])
    assert all(row["worked_explanation_accessed"] is False for row in result["rows"])
    assert all(row["target_section_status"] in {
        "lexical_candidate_requires_review", "unresolved_section_requires_review"
    } for row in result["rows"])
