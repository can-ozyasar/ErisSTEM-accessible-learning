import importlib.util
import json
from pathlib import Path
from typing import ClassVar

import pytest


def runner_module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "tts_chatterbox_v3_reference_runner.py"
    spec = importlib.util.spec_from_file_location("tts_chatterbox_v3_reference_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_v3_runner_keeps_source_revision_and_gold_contract_bounded(tmp_path: Path):
    module = runner_module()
    gold = tmp_path / "tts-gold-v1.json"
    gold.write_text(json.dumps({"schema_version": "tts-gold-v1", "items": [{
        "id": "formula-1", "kind": "formula", "expected_spoken_text": "x karesi eşittir dört",
    }]}), encoding="utf-8")

    assert module.SOURCE_REVISION == "678712b026da89058feb010886de23983cc8563b"
    assert module.load_gold(gold) == [{"id": "formula-1", "text": "x karesi eşittir dört", "kind": "formula"}]


def test_v3_is_explicit_and_cannot_silently_fall_back_to_v2():
    module = runner_module()

    class FakeModel:
        calls: ClassVar[list[dict[str, str]]] = []

        @classmethod
        def from_local(cls, _checkpoint_dir, **kwargs):
            cls.calls.append(kwargs)
            return "v3-model"

    snapshot_calls = []

    def snapshot_download(**kwargs):
        snapshot_calls.append(kwargs)
        return "/private/pinned-model"

    assert module.load_v3(FakeModel, snapshot_download) == "v3-model"
    assert FakeModel.calls == [{"device": "cuda", "t3_model": "v3"}]
    assert snapshot_calls == [{
        "repo_id": "ResembleAI/chatterbox", "repo_type": "model",
        "revision": "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18",
        "allow_patterns": module.MODEL_FILES,
    }]


def test_reference_filter_rejects_clipped_short_or_malformed_audio():
    module = runner_module()

    class FakeTorch:
        float32 = object()

        @staticmethod
        def as_tensor(*_args, **_kwargs):
            raise ValueError("bad data")

    assert module.viable_reference_waveform({"array": [], "sampling_rate": 24000}, FakeTorch(), object()) is None


def test_reference_selection_has_a_hard_scan_limit():
    module = runner_module()
    data = [{"audio": {"array": [], "sampling_rate": 24000}}] * module.MAX_REFERENCE_CANDIDATES

    class RejectingTorch:
        float32 = object()

        @staticmethod
        def as_tensor(*_args, **_kwargs):
            raise ValueError("bad data")

    with pytest.raises(module.TtsInputError, match="no_technically_valid"):
        module.select_reference(data, RejectingTorch(), object())
