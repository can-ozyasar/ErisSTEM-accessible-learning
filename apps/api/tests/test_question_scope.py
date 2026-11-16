"""Visual-source questions stay outside the AYT text coaching pilot."""

from app.question_scope import (
    AccessibilityAndScopeFilter,
    visual_cue_in_text,
    visual_dependency_reasons,
)


def test_map_table_and_image_references_are_out_of_scope():
    for stem in (
        "Aşağıdaki haritaya göre hangi cephe gösterilmiştir?",
        "Verilen tabloda hangi yıl eksiktir?",
        "Görselde gösterilen olay hangisidir?",
        "Bu fotoğraftaki kişi kimdir?",
        "Aşağıdaki şekilde hangi devletler görülüyor?",
        "Aşağıda verilen haritaya göre cepheleri karşılaştırınız.",
        "Haritaya göre hangi bölge seçilmiştir?",
        "Şekildeki olay hangi yılda yaşanmıştır?",
        "3 Mart 1924 inkılaplarını gösteren şemada soru işaretinin yerine ne gelmelidir?",
    ):
        assert visual_cue_in_text(stem), stem


def test_history_prose_does_not_become_visual_question():
    for stem in (
        "Osmanlı yönetim şekilleri hakkında bilgi veriniz.",
        "Bu şekilde siyasi hâkimiyet güçlenmiştir.",
        "Resim ve heykel sanatında ilerleyen uygarlık hangisidir?",
    ):
        assert not visual_cue_in_text(stem), stem


def test_embedded_image_and_structured_choice_table_are_out_of_scope():
    assert visual_dependency_reasons({"parts": [], "visuals": [{"id": "map"}]}) == [
        "embedded_visual",
    ]
    # An image in the question box is excluded even if the stem can be read alone.
    assert visual_dependency_reasons({"stem": "Bu olay hangi yıl yaşandı?", "visuals": [{"id": "map"}]}) == [
        "embedded_visual",
    ]
    assert visual_dependency_reasons({"parts": [{"kind": "choice_table_header", "text": "I II III"}]}) == [
        "structured_table",
    ]


def test_visual_reference_in_choice_is_out_of_scope():
    question = {
        "stem": "Kurtuluş Savaşı ile ilgili hangisine ulaşılabilir?",
        "choices": [
            {"label": "A", "text": "Haritada gösterilen cephe"},
            {"label": "B", "text": "Diğer ifade"},
        ],
    }
    assert "referenced_visual" in visual_dependency_reasons(question)


def test_text_question_whitelist_and_target_scope():
    gate = AccessibilityAndScopeFilter(
        target_section_ids={"3.1", "3.2"}, page_ranges=[(100, 120)],
    )
    for question in (
        {"stem": "I. TBMM açılmıştır. II. Saltanat kaldırılmıştır. Hangileri doğrudur?"},
        {"stem": "Boş bırakılan yere aşağıdakilerden hangisi gelmelidir?"},
        {"stem": "Bu olay hangi yüzyılda gerçekleşmiştir?"},
    ):
        decision = gate.evaluate(question, section_id="3.1")
        assert decision.eligible
        assert decision.format_tags
    assert not gate.evaluate({"stem": "Yukarıdaki haritaya göre hangi cephe?"}, page=110).eligible
    assert not gate.evaluate({"stem": "Bu olay hangi yılda oldu?"}, section_id="1.3").eligible
    assert not gate.evaluate({"stem": "Bu olay hangi yılda oldu?"}).eligible
