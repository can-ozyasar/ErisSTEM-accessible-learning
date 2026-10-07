import importlib.util
import json
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


def test_prepare_notebook_package_is_private_and_binds_the_declared_dataset(tmp_path: Path, monkeypatch):
    module = kaggle_ops_module()
    private = tmp_path / "private"
    private.mkdir()
    runners = tmp_path / "experiments" / "kaggle"
    runners.mkdir(parents=True)
    runner = runners / "runner.py"
    dataset = "muhammedcanozyasar/private-benchmark-v2"
    runner.write_text(f"INPUT = '/kaggle/input/datasets/{dataset}'\n", encoding="utf-8")
    monkeypatch.setattr(module, "private_root", lambda: private)
    monkeypatch.setattr(module, "repo_root", lambda: tmp_path)

    package = module.prepare_notebook_package(
        "muhammedcanozyasar/private-notebook-v2", dataset, runner, "Private benchmark", enable_internet=True
    )

    metadata = module.load_kernel_metadata(package, "muhammedcanozyasar/private-notebook-v2", dataset)
    assert metadata["is_private"] == "true"
    assert metadata["enable_gpu"] == "true"
    assert metadata["dataset_sources"] == [dataset]
    assert (package / "run.py").is_file()


def test_prepare_notebook_rejects_runner_with_different_dataset(tmp_path: Path, monkeypatch):
    module = kaggle_ops_module()
    private = tmp_path / "private"
    private.mkdir()
    runners = tmp_path / "experiments" / "kaggle"
    runners.mkdir(parents=True)
    runner = runners / "runner.py"
    runner.write_text("INPUT = 'another/dataset'\n", encoding="utf-8")
    monkeypatch.setattr(module, "private_root", lambda: private)
    monkeypatch.setattr(module, "repo_root", lambda: tmp_path)

    with pytest.raises(ValueError, match="eşleşmiyor"):
        module.prepare_notebook_package(
            "muhammedcanozyasar/private-notebook-v2",
            "muhammedcanozyasar/private-benchmark-v2",
            runner,
            "Private benchmark",
            enable_internet=False,
        )


def test_symbol_prediction_validation_requires_exactly_the_sealed_input_ids(tmp_path: Path, monkeypatch):
    module = kaggle_ops_module()
    private = tmp_path / "private"
    private.mkdir()
    manifest = private / "symbol-cell-manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": "symbol-cell-benchmark-input-v1", "assets": [{"id": "cell-a"}]}),
        encoding="utf-8",
    )
    predictions = private / "symbol_predictions.json"
    predictions.write_text(
        json.dumps(
            {
                "schema_version": "symbol-cell-predictions-v1",
                "candidate": "candidate-a",
                "predictions": [{"id": "cell-a", "prediction": "∈", "status": "completed"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "private_root", lambda: private)

    ids = module.symbol_input_ids(manifest)
    module.validate_symbol_predictions(predictions, ids)

    predictions.write_text(
        json.dumps(
            {
                "schema_version": "symbol-cell-predictions-v1",
                "candidate": "candidate-a",
                "predictions": [{"id": "unknown", "prediction": "∈", "status": "completed"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="geçersiz"):
        module.validate_symbol_predictions(predictions, ids)
