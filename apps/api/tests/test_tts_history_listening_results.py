import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).parents[3] / "experiments/kaggle/tts_history_listening_results.py"
    spec = importlib.util.spec_from_file_location("tts_history_listening_results", path)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(loaded)
    return loaded


def fixtures(tmp_path):
    manifest = tmp_path / "manifest.json"
    mapping = tmp_path / "mapping.json"
    response = tmp_path / "response.json"
    manifest.write_text(json.dumps({"schema_version": "tts-history-eval-v1", "items": [
        {"id": "one", "kind": "text"}, {"id": "two", "kind": "exercise"}
    ]}), encoding="utf-8")
    mapping.write_text(json.dumps({"input_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(), "assignments": {
        "one": {"A": "piper", "B": "chatterbox"},
        "two": {"A": "chatterbox", "B": "piper"},
    }}), encoding="utf-8")
    response.write_text(json.dumps({"schema_version": "tts-history-listener-v1", "reviewer": "listener", "entries": [
        {"id": "one", "preferred": "B", "accurate_a": "no", "accurate_b": "yes", "note": "duraklama"},
        {"id": "two", "preferred": "A", "accurate_a": "yes", "accurate_b": "unsure", "note": ""},
    ]}), encoding="utf-8")
    return manifest, mapping, response


def test_unblinds_and_keeps_accuracy_separate(tmp_path):
    manifest, mapping, response = fixtures(tmp_path)
    report = module().evaluate(manifest, mapping, [response])
    assert report["preferences"] == {"chatterbox": 2}
    assert report["accuracy"]["chatterbox"] == {"yes": 2}
    assert report["accuracy"]["piper"] == {"no": 1, "unsure": 1}
    assert report["notes"] == [{"reviewer": "listener", "id": "one", "note": "duraklama"}]


def test_rejects_missing_or_duplicate_items(tmp_path):
    manifest, mapping, response = fixtures(tmp_path)
    payload = json.loads(response.read_text(encoding="utf-8"))
    payload["entries"][1] = payload["entries"][0]
    response.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="mismatched_listener_ids"):
        module().evaluate(manifest, mapping, [response])
