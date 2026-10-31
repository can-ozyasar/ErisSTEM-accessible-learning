from app.pipeline.ogm_ayt_page_classifier import classify


def test_solution_and_answer_pages_are_not_test_candidates():
    assert classify("Tarih ÇÖZÜMLÜ SORULAR Çözüm: Cevap: B") == "solved_or_explained"
    assert classify("CEVAP ANAHTARI 1 A 2 B") == "answer_key"
    assert classify("Tarih 2. TEST 1. soru") == "test_candidate"
