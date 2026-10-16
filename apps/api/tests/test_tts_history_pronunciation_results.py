import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).parents[3] / "experiments/kaggle/tts_history_pronunciation_results.py"
    spec = importlib.util.spec_from_file_location("tts_history_pronunciation_results", path)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(loaded)
    return loaded


def fixture_paths(tmp_path):
    manifest = tmp_path / "manifest.json"
    mapping = tmp_path / "mapping.json"
    response = tmp_path / "response.json"
    manifest.write_text(json.dumps({"experiment": "same-run-source-label-pronunciation-v1", "items": [
        {"id": "source-control"}, {"id": "source-normalized"}
    ]}), encoding="utf-8")
    mapping.write_text(json.dumps({"schema_version": "tts-history-pronunciation-mapping-v1",
        "input_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "assignments": {"source": {"A": "normalized", "B": "control"}}}), encoding="utf-8")
    response.write_text(json.dumps({"schema_version": "tts-history-pronunciation-listener-v1",
        "reviewer": "listener", "entries": [{"id": "source", "preferred": "A",
        "accurate_a": "yes", "accurate_b": "no", "note": "A sesi kaynak ce dedi"}]}), encoding="utf-8")
    return manifest, mapping, response


def test_unblinds_pronunciation_separately_from_accuracy(tmp_path):
    report = module().evaluate(*fixture_paths(tmp_path))
    assert report["preference"] == {"normalized": 1}
    assert report["accuracy"] == {"control": {"no": 1}, "normalized": {"yes": 1}}


def test_rejects_missing_note(tmp_path):
    manifest, mapping, response = fixture_paths(tmp_path)
    payload = json.loads(response.read_text(encoding="utf-8"))
    payload["entries"][0]["note"] = ""
    response.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid_pronunciation_rating"):
        module().evaluate(manifest, mapping, response)
