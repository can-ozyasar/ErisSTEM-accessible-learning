from collections import Counter

from app.pipeline.bootstrap_tts_evaluation_gold import calibration_gold


def test_original_tts_calibration_gold_is_balanced_and_not_a_training_corpus():
    gold = calibration_gold()

    assert gold.schema_version == "tts-gold-v1"
    assert len(gold.items) == 60
    assert Counter(item.kind for item in gold.items) == {
        "text": 12,
        "formula": 12,
        "table": 12,
        "chart": 12,
        "exercise": 12,
    }
    assert all(item.critical_tokens for item in gold.items)
