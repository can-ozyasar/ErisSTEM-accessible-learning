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


def test_ancient_date_and_source_caption_are_prepared_for_turkish_voice():
    source = ("Pişmiş topraktan yapılan tekerlekli bir at, MÖ VI. yüzyıl, "
              "Metropolitan Art Museum, New York. (Bilim insanları, Antik Yunan Dönemi’ne ait "
              "diğer örneklerinden hareketle bu tekerlekli atın oyuncak olarak kullanıldığını düşünmektedir.)")
    spoken = history_spoken_text(source)
    assert "Milattan önce altıncı yüzyıl" in spoken
    assert "Metropoliten Art Müziyum, New York" in spoken
    assert "Antik Yunan Dönemi’ne" in spoken
    assert history_spoken_text(spoken) == spoken
    assert "MÖ VI. yüzyıl" in source


def test_only_valid_roman_centuries_and_exact_institution_name_are_changed():
    assert history_spoken_text("IV. yüzyıl, XXI. yüzyıl") == "dördüncü yüzyıl, yirmi birinci yüzyıl"
    assert history_spoken_text("VX. yüzyıl, Bölüm VI., Metropolitan sanat müzesi") == "VX. yüzyıl, Bölüm VI., Metropolitan sanat müzesi"
    assert history_spoken_text("Metropolitan Art Museum") == "Metropoliten Art Müziyum"
