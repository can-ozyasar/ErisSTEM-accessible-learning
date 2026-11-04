from app.pipeline.ogm_ayt_page_classifier import build, classify


def test_solution_and_answer_pages_are_not_test_candidates():
    assert classify("Tarih ÇÖZÜMLÜ SORULAR Çözüm: Cevap: B") == "solved_or_explained"
    assert classify("CEVAP ANAHTARI 1 A 2 B") == "answer_key"
    assert classify("Tarih 2. TEST 1. soru") == "test_candidate"


def test_build_marks_unheaded_page_inside_test_run_as_continuation(tmp_path):
    source = tmp_path / "search_config.js"
    source.write_text(
        'var textForPages = ["Tarih ve Zaman 1. Test 1. soru", "Tarih ve Zaman 2. soru", "Tarih ve Zaman Çözümlü Sorular"];',
        encoding="utf-8",
    )
    result = build(source)
    assert [row["category"] for row in result["pages"]] == ["test_candidate", "test_continuation", "solved_or_explained"]
