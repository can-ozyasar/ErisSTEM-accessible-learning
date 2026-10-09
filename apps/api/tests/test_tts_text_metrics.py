from app.pipeline.tts_text_metrics import speech_character_accuracy, speech_tokens


def test_turkish_speech_normalization_ignores_sentence_punctuation():
    assert speech_tokens("İkinci sütun: Birleşim.") == ["ikinci", "sütun", "birleşim"]
    assert speech_character_accuracy("İkinci sütun: Birleşim.", "ikinci sütun birleşim") == 1


def test_speech_normalization_keeps_mathematical_operators():
    assert speech_tokens("A ∈ B") == ["a", "∈", "b"]
    assert speech_character_accuracy("A ∈ B", "A B") < 1


def test_turkish_dotless_i_is_not_folded_to_dotted_i():
    assert speech_tokens("IRMAK") == ["ırmak"]
    assert speech_tokens("İRMİK") == ["irmik"]
