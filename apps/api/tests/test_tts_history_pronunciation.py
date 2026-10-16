import importlib
import hashlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def pilot(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[3] / "experiments/kaggle"))
    return importlib.import_module("tts_history_pronunciation")


def test_source_text_is_kept_separate_from_spoken_variants(pilot):
    source = json.loads(pilot.SOURCE.read_text(encoding="utf-8"))
    manifest = pilot.build_manifest(source)
    assert manifest["experiment"] == "same-run-source-label-pronunciation-v1"
    assert len(manifest["items"]) == 6
    by_id = {item["id"]: item for item in manifest["items"]}
    assert "Kaynak C." in by_id["history-caption-01-control"]["expected_spoken_text"]
    assert "Kaynak ce." in by_id["history-caption-01-normalized"]["expected_spoken_text"]
    assert "Kaynak A'yı" in by_id["history-question-01-control"]["expected_spoken_text"]
    assert "A kaynağını" in by_id["history-question-01-normalized"]["expected_spoken_text"]
    for item in manifest["items"]:
        assert all(token in item["expected_spoken_text"] for token in item["critical_tokens"])


def test_wrong_owner_never_starts_remote_pronunciation_job(pilot, monkeypatch):
    monkeypatch.setattr(pilot, "prepare", lambda: {"pairs": 3})
    monkeypatch.setattr(pilot.kaggle_ops, "verify", lambda: {"authenticated_user": "someone_else"})
    monkeypatch.setattr(pilot.kaggle_ops, "upload_dataset", lambda *_args: pytest.fail("uploaded"))
    with pytest.raises(ValueError, match="farklı"):
        pilot.main(["run"])


def test_blind_packet_requires_all_verified_wavs(pilot, monkeypatch, tmp_path):
    source = json.loads(pilot.SOURCE.read_text(encoding="utf-8"))
    manifest = tmp_path / "tts-history-eval-v1.json"
    manifest.write_text(json.dumps(pilot.build_manifest(source)), encoding="utf-8")
    monkeypatch.setattr(pilot, "MANIFEST", manifest)
    monkeypatch.setattr(pilot, "PACKET", tmp_path / "packet")
    audio = tmp_path / "audio"
    audio.mkdir()
    records = []
    for item in json.loads(manifest.read_text(encoding="utf-8"))["items"]:
        payload = b"RIFF" + item["id"].encode()
        (audio / f"{item['id']}.wav").write_bytes(payload)
        records.append({"id": item["id"], "audio_sha256": hashlib.sha256(payload).hexdigest()})
    report = {"input_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
              "items_failed": 0, "records": records}
    page = pilot.build_packet(audio, report)
    assert page.exists()
    assert len(list(page.parent.glob("*.wav"))) == 6
    assert "history-caption-01-normalized" not in page.read_text(encoding="utf-8")
    assert len(json.loads((page.parent / "mapping.json").read_text(encoding="utf-8"))["assignments"]) == 3
