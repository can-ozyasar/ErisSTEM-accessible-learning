import importlib.util
import json
import sys
import wave
from pathlib import Path

import pytest
from pydantic import ValidationError


def corpus_module():
    path = Path(__file__).parents[1] / "app" / "pipeline" / "tts_training_corpus.py"
    spec = importlib.util.spec_from_file_location("tts_training_corpus", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_wav(path: Path, *, channels: int = 1, sample_rate: int = 24_000, seconds: float = 1) -> None:
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * channels * frames)


def valid_payload() -> dict:
    return {
        "schema_version": "tts-training-corpus-v1",
        "consent": {
            "speaker_reference": "speaker-001",
            "source": "self-recorded",
            "adult_consent_attested": True,
            "voice_model_training_consent_attested": True,
            "withdrawal_process_available": True,
        },
        "recordings": [
            {
                "id": "train-1",
                "audio_path": "audio/train-1.wav",
                "transcript": "özel ders metni",
                "kind": "formula",
                "split": "train",
            },
            {
                "id": "validation-1",
                "audio_path": "audio/validation-1.wav",
                "transcript": "özel ders metni iki",
                "kind": "table",
                "split": "validation",
            },
        ],
    }


def test_voice_training_corpus_returns_a_content_free_structure_report(tmp_path: Path):
    module = corpus_module()
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    write_wav(audio_dir / "train-1.wav")
    write_wav(audio_dir / "validation-1.wav")
    corpus = module.VoiceTrainingCorpus.model_validate(valid_payload())

    report = module.validate_voice_training_corpus(corpus, tmp_path)

    assert report["contains_audio"] is False
    assert report["contains_transcripts"] is False
    assert report["splits"] == {"train": 1, "validation": 1}
    assert report["kinds"] == {"formula": 1, "table": 1}
    assert "özel ders metni" not in json.dumps(report, ensure_ascii=False)


def test_voice_training_corpus_requires_explicit_voice_training_consent():
    module = corpus_module()
    payload = valid_payload()
    payload["consent"]["voice_model_training_consent_attested"] = False

    with pytest.raises(ValidationError, match="incomplete_voice_training_consent"):
        module.VoiceTrainingCorpus.model_validate(payload)


def test_voice_training_corpus_rejects_stereo_audio(tmp_path: Path):
    module = corpus_module()
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    write_wav(audio_dir / "train-1.wav", channels=2)
    write_wav(audio_dir / "validation-1.wav")
    corpus = module.VoiceTrainingCorpus.model_validate(valid_payload())

    with pytest.raises(ValueError, match="unsupported_wav_format"):
        module.validate_voice_training_corpus(corpus, tmp_path)
