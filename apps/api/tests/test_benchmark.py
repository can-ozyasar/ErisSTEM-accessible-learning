from app.pipeline.benchmark import character_error_rate, token_f1


def test_text_metrics():
    assert character_error_rate("Merhaba dünya", "Merhaba dünya") == 0
    assert token_f1("a bölü b", "a bölü b") == 1
    assert token_f1("a bölü b", "a çarpı b") < 1
