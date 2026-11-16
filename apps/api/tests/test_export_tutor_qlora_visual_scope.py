"""Research export scope and early-stage evidence checks."""

import pytest

from app.pipeline.export_tutor_qlora_pilot import _canonical_records, _question_texts


def test_visual_transcription_is_not_exportable():
    transcription = {
        "schema": "ogm-ayt-private-transcription-v1",
        "rows": [{
            "candidate_id": "q-map",
            "question": {"stem": "Aşağıdaki haritaya göre hangi cephe?", "choices": []},
        }],
    }
    assert _question_texts(transcription) == {}


def test_early_prompt_can_be_source_free_but_evidence_stage_cannot():
    base = {"question_id": "q1", "case": "soruyu_anlama",
            "guide_response": "Bu soru senden neyi karşılaştırmanı istiyor?",
            "source_ids": [], "evidence_quotes": [], "early_answer_disclosed": False}
    draft = {"answer_key_accessed": False, "worked_explanation_accessed": False,
             "records": [base]}
    assert _canonical_records(draft, {"q1": "Soru metni"})[0]["quotes"] == []
    draft["records"][0]["case"] = "kanitla_bag_kur"
    with pytest.raises(ValueError, match="kanıt sayısı"):
        _canonical_records(draft, {"q1": "Soru metni"})
