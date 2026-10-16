import importlib
import hashlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def prosody(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[3] / "experiments/kaggle"))
    return importlib.import_module("tts_history_prosody")


def test_pairs_change_only_punctuation_or_case(prosody):
    source = json.loads(prosody.SOURCE.read_text(encoding="utf-8"))
    manifest = prosody.build_manifest(source)
    assert manifest["experiment"] == "same-run-punctuation-only-paired-v1"
    assert len(manifest["items"]) == 10
    for index in range(0, 10, 2):
        control, alternative = manifest["items"][index:index + 2]
        assert prosody.words(control["expected_spoken_text"]) == prosody.words(alternative["expected_spoken_text"])
        assert control["id"].endswith("-control")
        assert alternative["id"].endswith("-punctuation")


def test_rejects_word_changes(prosody):
    source = json.loads(prosody.SOURCE.read_text(encoding="utf-8"))
    original = prosody.VARIANTS["history-caption-01"]
    try:
        prosody.VARIANTS["history-caption-01"] = original.replace("altıncı", "yedinci")
        with pytest.raises(ValueError, match="yalnız noktalama"):
            prosody.build_manifest(source)
    finally:
        prosody.VARIANTS["history-caption-01"] = original


def test_packet_requires_every_checksum_and_hides_variant_assignment(prosody, monkeypatch, tmp_path):
    manifest = tmp_path / "tts-history-eval-v1.json"
    source = json.loads(prosody.SOURCE.read_text(encoding="utf-8"))
    manifest.write_text(json.dumps(prosody.build_manifest(source)), encoding="utf-8")
    monkeypatch.setattr(prosody, "MANIFEST", manifest)
    monkeypatch.setattr(prosody, "PACKET", tmp_path / "listening")
    audio = tmp_path / "audio"
    audio.mkdir()
    records = []
    for item in json.loads(manifest.read_text(encoding="utf-8"))["items"]:
        payload = b"RIFF" + item["id"].encode("utf-8")
        (audio / f"{item['id']}.wav").write_bytes(payload)
        records.append({"id": item["id"], "audio_sha256": hashlib.sha256(payload).hexdigest()})
    report = {"input_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
              "items_failed": 0, "records": records}
    page = prosody.build_packet(audio, report)
    assert page.exists()
    assert len(list(page.parent.glob("*.wav"))) == 10
    html = page.read_text(encoding="utf-8")
    assert "Somut duraklama/telaffuz notu" in html
    assert "history-caption-01-punctuation" not in html
    mapping = json.loads((page.parent / "mapping.json").read_text(encoding="utf-8"))
    assert len(mapping["assignments"]) == 5
