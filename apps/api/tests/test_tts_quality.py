from app.pipeline.tts_quality import TtsCandidateManifest, TtsGoldManifest, evaluate_tts_candidate


def gold(count: int = 1) -> TtsGoldManifest:
    return TtsGoldManifest.model_validate({
        "schema_version": "tts-gold-v1",
        "items": [{"id": f"u-{number}", "kind": "formula", "expected_spoken_text": "x karesi eşittir dört", "critical_tokens": ["karesi", "eşittir"]} for number in range(count)],
    })


def test_tts_report_never_exposes_private_reference_or_candidate_text():
    candidate = TtsCandidateManifest.model_validate({
        "schema_version": "tts-candidate-v1", "candidate": "voice-a",
        "results": [{"id": "u-0", "observed_spoken_text": "x karesi eşittir dört"}],
    })

    report = evaluate_tts_candidate(gold(), candidate)

    assert report["contains_document_content"] is False
    assert report["pronunciation_accuracy"] == report["critical_token_accuracy"] == 1
    assert "expected_spoken_text" not in str(report)
    assert report["decision"] == "tts-candidate-blocked"


def test_tts_gate_blocks_a_wrong_critical_math_token_even_with_adequate_sample_count():
    candidate = TtsCandidateManifest.model_validate({
        "schema_version": "tts-candidate-v1", "candidate": "voice-a",
        "results": [{"id": f"u-{number}", "observed_spoken_text": "x küpü eşittir dört"} for number in range(50)],
    })

    report = evaluate_tts_candidate(gold(50), candidate)

    assert report["critical_token_accuracy"] < 1
    assert report["decision"] == "tts-candidate-blocked"
