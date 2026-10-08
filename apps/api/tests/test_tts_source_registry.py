from app.pipeline.tts_source_registry import TtsSourceRegistry, validate_tts_source_registry


def source(**overrides):
    value = {
        "source_id": "target-voice-001", "dataset_handle": "omersaidd/tts_nisan_kumru_tur",
        "snapshot_revision": "a1b2c3d4", "role": "single-speaker-voice-training",
        "source_url": "https://huggingface.co/datasets/omersaidd/tts_nisan_kumru_tur",
        "speaker_reference": "voice-source-001",
    }
    value.update(overrides)
    return value


def test_voice_training_is_blocked_until_all_provenance_and_permission_safeguards_exist():
    registry = TtsSourceRegistry.model_validate({"schema_version": "tts-training-source-registry-v1", "sources": [source()]})
    report = validate_tts_source_registry(registry)

    assert report["training_decision"] == "voice-training-blocked"
    assert report["records"][0]["decision"] == "blocked-missing-provenance-or-permission"
    assert "voice-model-training-permission" in report["records"][0]["missing_safeguards"]


def test_voice_training_source_can_enter_private_corpus_intake_only_after_complete_attestations():
    registry = TtsSourceRegistry.model_validate({"schema_version": "tts-training-source-registry-v1", "sources": [source(
        single_speaker_attested=True, audio_rights_attested=True, transcript_rights_attested=True,
        voice_model_training_permission_attested=True, withdrawal_process_attested=True,
        permission_record_id="permission-2026-001",
    )]})
    report = validate_tts_source_registry(registry)

    assert report["training_decision"] == "private-corpus-intake-permitted"
    assert report["eligible_voice_training_source_ids"] == ["target-voice-001"]


def test_math_source_has_a_text_analysis_role_and_never_becomes_a_voice_source_by_accident():
    registry = TtsSourceRegistry.model_validate({"schema_version": "tts-training-source-registry-v1", "sources": [source(
        source_id="khan-math", dataset_handle="ysdede/khanacademy-turkish-math", role="math-text-analysis",
        speaker_reference=None, transcript_rights_attested=True,
    )]})
    report = validate_tts_source_registry(registry)

    assert report["training_decision"] == "voice-training-blocked"
    assert report["records"][0]["decision"] == "eligible-for-text-analysis-only"
