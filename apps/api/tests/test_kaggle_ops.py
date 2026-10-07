import importlib.util
from pathlib import Path

import pytest


def kaggle_ops_module():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "kaggle_ops.py"
    spec = importlib.util.spec_from_file_location("kaggle_ops", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_validate_handle_accepts_owner_and_slug_only():
    module = kaggle_ops_module()

    assert module.validate_handle("muhammedcanozyasar/private-benchmark-v1") == "muhammedcanozyasar/private-benchmark-v1"
    with pytest.raises(ValueError):
        module.validate_handle("https://www.kaggle.com/datasets/user/data")


def test_private_directory_rejects_paths_outside_private_root(tmp_path: Path, monkeypatch):
    module = kaggle_ops_module()
    private = tmp_path / "private"
    private.mkdir()
    allowed = private / "dataset"
    allowed.mkdir()
    monkeypatch.setattr(module, "private_root", lambda: private)

    assert module.private_directory(allowed) == allowed
    with pytest.raises(ValueError):
        module.private_directory(tmp_path)
