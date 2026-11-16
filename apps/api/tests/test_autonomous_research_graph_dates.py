"""A year must describe the named event, not another event in its sentence."""

from app.pipeline.build_autonomous_research_graph import (
    _complete_sentences,
    _event_titles,
    _event_year_action,
)


def test_named_event_year_requires_direct_local_binding():
    direct = "Türkiye 1928’de imzalanan Paris Sözleşmesi’yle yeni bir döneme girdi."
    unrelated = "Sykes-Picot Antlaşması’na göre İngiltere 1918’de Musul’u işgal etti."
    long_gap = ("10 Ağustos 1913’te Bulgaristan, Yunanistan, Sırbistan ve "
                "Karadağ arasında imzalanan Bükreş Antlaşması’yla savaş bitti.")
    assert _event_year_action(direct, "Paris Sözleşmesi", "1928") == "signed"
    assert _event_year_action("1923’te Lozan Barış Antlaşması imzalandı.",
                              "Lozan Barış Antlaşması", "1923") == "signed"
    assert _event_year_action(unrelated, "Sykes-Picot Antlaşması", "1918") is None
    assert _event_year_action(long_gap, "Bükreş Antlaşması", "1913") is None


def test_event_title_does_not_swallow_intervening_clause():
    sentence = ("10 Ağustos 1913’te Bulgaristan, Yunanistan, Sırbistan ve "
                "Karadağ arasında imzalanan Bükreş Antlaşması’yla savaş bitti.")
    assert _event_titles(sentence) == ["Bükreş Antlaşması"]


def test_range_is_not_a_single_event_year():
    sentence = "1877-1878 Osmanlı-Rus Savaşı sonrasında sınırlar değişti."
    assert _event_year_action(sentence, "Osmanlı-Rus Savaşı", "1878") is None


def test_sentence_evidence_is_not_cut_at_display_limit():
    prefix = "Önceki ilişkiler anlatıldı. " * 18
    full = prefix + "1921’de Türk-Afgan Dostluk Antlaşması imzalandı."
    assert len(full) > 520
    assert _complete_sentences(full)[-1] == "1921’de Türk-Afgan Dostluk Antlaşması imzalandı."
