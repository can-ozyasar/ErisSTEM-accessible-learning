import importlib.util
import json
from pathlib import Path

import pytest


def runner_module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "tts_chatterbox_runner.py"
    spec = importlib.util.spec_from_file_location("tts_chatterbox_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_tts_runner_accepts_bounded_sealed_gold_manifest(tmp_path: Path):
    module = runner_module()
    gold = tmp_path / "tts-gold-v1.json"
    gold.write_text(
        json.dumps(
            {
                "schema_version": "tts-gold-v1",
                "items": [
                    {
                        "id": "formula-1",
                        "kind": "formula",
                        "expected_spoken_text": "x karesi eşittir dört",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert module.load_gold(gold) == [
        {"id": "formula-1", "text": "x karesi eşittir dört", "kind": "formula"}
    ]


def test_tts_runner_rejects_path_like_gold_item_id(tmp_path: Path):
    module = runner_module()
    gold = tmp_path / "tts-gold-v1.json"
    gold.write_text(
        json.dumps(
            {
                "schema_version": "tts-gold-v1",
                "items": [
                    {
                        "id": "../../unexpected",
                        "kind": "text",
                        "expected_spoken_text": "doğrulanmış metin",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(module.TtsInputError, match="invalid_tts_gold_item"):
        module.load_gold(gold)
