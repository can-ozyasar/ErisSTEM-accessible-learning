"""Behavioral regression checks for a calm, source-bound history coach."""
import re

from app.tutor_coach import CoachContext, coach


def context():
    return CoachContext(question_id="teacher-benchmark-1", question_text="Bir olayın nedenini soran tarih sorusu.",
                        choice_text="Bir yorum ifadesi", section_title="AYT Tarih", source_ids=["meb-atom-1"],
                        evidence="Kaynak, olayın ortaya çıkış nedenini açıkça belirtir.", error_type="neden_sonuc")


def test_teacher_style_benchmark_is_supportive_specific_and_answer_safe():
    cases = {
        "Tarihleri karıştırdım, hangisi önceydi?": ("temporal_confusion", "temporal_order"),
        "Neden ile sonuç arasındaki bağı kuramadım.": ("causal_confusion", "cause_effect_chain"),
        "Bu konu çok karıştı, yardım eder misin?": ("needs_chunking", "reduce_load"),
        "Bence kesin doğru ama nedenini açıklayamıyorum.": ("needs_reasoning_check", "evidence_comparison"),
    }
    for learner_message, (expected_signal, expected_strategy) in cases.items():
        reply = coach(context(), None, learner_message, False, None, None)
        assert reply.learner_signal == expected_signal
        assert reply.strategy == expected_strategy
        assert reply.student_prompt.endswith("?")
        assert reply.student_prompt.count("?") == 1
        assert len(reply.short_spoken_text) <= 240
        assert reply.short_spoken_text.endswith("?")
        assert not re.search(r"doğru\s+(cevap|şık)|\bşık\s*[abcde]\b", reply.student_prompt, re.I)
        assert reply.source_ids == ["meb-atom-1"]


def test_teacher_style_does_not_pretend_to_know_when_source_is_missing():
    missing = CoachContext(**{**context().__dict__, "source_ids": [], "evidence": ""})
    reply = coach(missing, None, "Karıştırdım.", False, None, None)
    assert reply.abstain_reason == "approved_source_unavailable"
    assert "öğretmen onaylı MEB kanıtı henüz yok" in reply.student_prompt


def test_repeated_wrong_choice_reanchors_to_source_instead_of_repeating_the_same_hint():
    repeated = CoachContext(**{**context().__dict__, "repeat_attempts": 2})
    reply = coach(repeated, "kanitla_bag_kur", "Hâlâ aynı şıktan eminim.", False, "A", None)
    assert reply.strategy == "source_reanchor"
    assert reply.student_prompt.count("?") == 1
