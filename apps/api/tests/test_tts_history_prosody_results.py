import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).parents[3] / "experiments/kaggle/tts_history_prosody_results.py"
    spec = importlib.util.spec_from_file_location("tts_history_prosody_results", path)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(loaded)
    return loaded


def test_synthetic_unblinding_works_without_private_user_files(tmp_path):
    manifest = tmp_path / "manifest.json"
    mapping = tmp_path / "mapping.json"
    response = tmp_path / "response.json"
    manifest.write_text(json.dumps({"experiment": "same-run-punctuation-only-paired-v1", "items": [
        {"id": "caption-control"}, {"id": "caption-punctuation"}
    ]}), encoding="utf-8")
    mapping.write_text(json.dumps({"schema_version": "tts-history-prosody-mapping-v1",
        "input_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "assignments": {"caption": {"A": "control", "B": "punctuation"}}}), encoding="utf-8")
    response.write_text(json.dumps({"schema_version": "tts-history-prosody-listener-v1",
        "reviewer": "listener", "entries": [{"id": "caption", "preferred": "B",
        "accurate_a": "no", "accurate_b": "yes", "note": "B daha anlaşılır"}]}), encoding="utf-8")
    report = module().evaluate(manifest, mapping, response)
    assert report["preference"] == {"punctuation": 1}
    assert report["accuracy"] == {"control": {"no": 1}, "punctuation": {"yes": 1}}
    aggregate = module().evaluate_many(manifest, mapping, [response])
    assert aggregate["preference"] == {"punctuation": 1}
    assert aggregate["independent_listener_count_verified"] is False


def test_real_private_response_is_source_bound_and_unblinded():
    root = Path(__file__).parents[3] / "data/private"
    manifest = root / "eristem_history_tts_prosody_v1/tts-history-eval-v1.json"
    mapping = root / "tts_history_prosody_listening_v1/mapping.json"
    response = root / "tts_history_prosody_listening_v1/history-prosody-canozyasar.json"
    if not response.exists():
        pytest.skip("Dinleyici yanıtı bu çalışma alanında yok")
    report = module().evaluate(manifest, mapping, response)
    assert report["preference"] == {"control": 3, "punctuation": 2}
    assert report["accuracy"]["control"] == {"yes": 4, "no": 1}
    assert report["accuracy"]["punctuation"] == {"yes": 3, "no": 2}


def test_rejects_omitted_rating(tmp_path):
    root = Path(__file__).parents[3] / "data/private"
    manifest = root / "eristem_history_tts_prosody_v1/tts-history-eval-v1.json"
    mapping = root / "tts_history_prosody_listening_v1/mapping.json"
    original = root / "tts_history_prosody_listening_v1/history-prosody-canozyasar.json"
    if not original.exists():
        pytest.skip("Dinleyici yanıtı bu çalışma alanında yok")
    payload = json.loads(original.read_text(encoding="utf-8"))
    payload["entries"][0]["accurate_a"] = ""
    response = tmp_path / "invalid.json"
    response.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid_prosody_rating"):
        module().evaluate(manifest, mapping, response)
