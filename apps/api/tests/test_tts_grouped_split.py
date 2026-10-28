import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[3] / "experiments/kaggle/tts_grouped_split.py"
spec = importlib.util.spec_from_file_location("tts_grouped_split", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def record(index, audio=None, text=None, seconds=7):
    return {
        "source_index": index,
        "decoded_audio_sha256": f"{audio if audio is not None else index:064x}",
        "normalized_text_sha256": f"{text if text is not None else index:064x}",
        "seconds": seconds,
    }


def test_transitive_duplicates_stay_together_and_split_is_stable():
    records = [record(i) for i in range(1, 101)]
    records[1] = record(2, audio=1)
    records[2] = record(3, text=2)
    split = module.split_records(records, seed=42)
    assert split == module.split_records(list(reversed(records)), seed=42)
    assert len({split["group_by_index"][i] for i in (1, 2, 3)}) == 1
    assert set(split["train"]).isdisjoint(split["validation"])
    assert set(split["train"]) | set(split["validation"]) == set(range(1, 101))
    assert {1, 2, 3} <= set(split["train"]) or {1, 2, 3} <= set(split["validation"])
    assert split["train"] and split["validation"]


def test_reference_is_distinct_training_group_and_deterministic():
    records = [record(i, seconds=5 if i % 3 == 0 else 7) for i in range(1, 101)]
    split = module.split_records(records, seed=7)
    for target in split["train"] + split["validation"]:
        reference = module.select_reference(target, records, split, seed=9)
        assert reference in split["train"]
        assert split["group_by_index"][reference] != split["group_by_index"][target]
        assert records[reference - 1]["seconds"] >= 6
        assert reference == module.select_reference(target, list(reversed(records)), split, seed=9)


def test_no_reference_and_invalid_records_fail_explicitly():
    records = [record(1)]
    split = module.split_records(records, seed=1)
    with pytest.raises(ValueError, match="no_distinct_training_reference"):
        module.select_reference(1, records, split, seed=1)
    with pytest.raises(ValueError, match="invalid_or_duplicate_source_index"):
        module.split_records([record(1), record(1)], seed=1)
    with pytest.raises(ValueError, match="invalid_duration"):
        module.split_records([record(1, seconds=float("nan"))], seed=1)
