from app.pipeline.tts_error_analysis import analyse_tts_errors
from app.pipeline.tts_quality import TtsCandidateManifest, TtsGoldManifest


def test_error_analysis_reports_only_aggregate_error_signals():
    gold = TtsGoldManifest.model_validate(
        {
            "schema_version": "tts-gold-v1",
            "items": [
                {
                    "id": "formula-01",
                    "kind": "formula",
                    "expected_spoken_text": "x karesi eşittir dört",
                    "critical_tokens": ["karesi", "eşittir"],
                },
                {
                    "id": "text-01",
                    "kind": "text",
                    "expected_spoken_text": "özel metin",
                    "critical_tokens": ["özel"],
                },
            ],
        }
    )
    candidate = TtsCandidateManifest.model_validate(
        {
            "schema_version": "tts-candidate-v1",
            "candidate": "voice-a",
            "results": [
                {"id": "formula-01", "observed_spoken_text": "x küpü eşittir dört"},
                {"id": "text-01", "observed_spoken_text": "özel metin"},
            ],
        }
    )

    report = analyse_tts_errors(gold, candidate)

    assert report["contains_document_content"] is False
    assert report["kinds"]["formula"]["critical_token_accuracy"] == 0.5
    assert report["kinds"]["text"]["exact_transcripts"] == 1
    assert report["investigation_priority"][0] == "formula"
    assert "karesi" not in str(report)
    assert "özel metin" not in str(report)
