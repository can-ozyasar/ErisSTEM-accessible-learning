from app.history_speech import history_spoken_text


def test_bare_source_labels_have_separate_turkish_letter_names():
    assert history_spoken_text("Kaynak C. Pişmiş toprak.") == "Kaynak ce. Pişmiş toprak."
    assert history_spoken_text("Kaynak B ve Kaynak C, bu konuyla ilgili") == "Kaynak be ve Kaynak ce, bu konuyla ilgili"
    assert history_spoken_text("Kaynak Ç ile Kaynak Ğ") == "Kaynak çe ile Kaynak yumuşak ge"
    assert history_spoken_text("Kaynak I, Kaynak İ ve Kaynak Ü") == "Kaynak ı, Kaynak i ve Kaynak ü"


def test_source_a_object_avoids_ayi_pronunciation():
    assert history_spoken_text("Kaynak A'yı yazan araştırmacı") == "A kaynağını yazan araştırmacı"
    assert history_spoken_text("Kaynak A’yı yazan araştırmacı") == "A kaynağını yazan araştırmacı"


def test_unrelated_letters_and_suffixes_are_untouched():
    assert history_spoken_text("C vitamini; Cumhuriyet; Kaynak C'nin") == "C vitamini; Cumhuriyet; Kaynak C'nin"
    assert history_spoken_text("Kaynak A'nın yazarı") == "Kaynak A'nın yazarı"
