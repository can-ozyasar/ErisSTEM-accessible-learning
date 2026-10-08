import importlib.util
import json
import re
import subprocess
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
        "muhammedcanozyasar/private-notebook-v2", dataset, runner, "Private Notebook V2", enable_internet=True
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
            "Private Notebook V2",
            enable_internet=False,
        )


def test_notebook_title_must_resolve_to_the_declared_kernel_slug():
    module = kaggle_ops_module()

    assert module.notebook_title_slug("Eristem Private Benchmark V2") == "eristem-private-benchmark-v2"
    with pytest.raises(ValueError, match="ASCII"):
        module.notebook_title_slug("ErişSTEM private benchmark")


def test_output_filename_pattern_allows_only_the_expected_filename_with_an_optional_run_directory():
    module = kaggle_ops_module()
    pattern = module.output_filename_pattern("run_metadata.json")

    assert re.fullmatch(pattern, "run_metadata.json")
    assert re.fullmatch(pattern, "run-1/run_metadata.json")
    assert not re.fullmatch(pattern, "run_metadata.json.bak")
    assert not re.fullmatch(pattern, "run-1/unrelated.json")


def test_output_filenames_pattern_matches_only_the_allowlisted_report_names():
    module = kaggle_ops_module()
    pattern = module.output_filenames_pattern(("run_metadata.json", "run_records.json"))

    assert re.fullmatch(pattern, "run-1/run_metadata.json")
    assert re.fullmatch(pattern, "run-1/run_records.json")
    assert not re.fullmatch(pattern, "run-1/audio.wav")


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


def test_download_summaries_ignores_kaggle_technical_log_but_keeps_it_out_of_manifest(tmp_path: Path, monkeypatch):
    module = kaggle_ops_module()
    destination = tmp_path / "download"
    kernel = "muhammedcanozyasar/private-notebook-v3"

    monkeypatch.setattr(module, "output_directory", lambda received_kernel: destination)
    monkeypatch.setattr(module, "kaggle_cli", lambda: "kaggle")

    def fake_run(command, **_kwargs):
        destination.mkdir(exist_ok=True)
        (destination / "run_metadata.json").write_text('{"candidate": "test"}', encoding="utf-8")
        (destination / "private-notebook-v3.log").write_text("technical log", encoding="utf-8")
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result_directory, attempts = module.download_summaries(kernel)

    assert result_directory == destination
    assert attempts == [
        {"filename": "run_metadata.json", "downloaded": True},
        {"filename": "run_records.json", "downloaded": False},
        {"filename": "structural_report.json", "downloaded": False},
        {"filename": "region_records.json", "downloaded": False},
        {"filename": "native_agreement_report.json", "downloaded": False},
    ]
    manifest = json.loads((destination / "download_manifest.json").read_text(encoding="utf-8"))
    assert [item["path"] for item in manifest["files"]] == ["run_metadata.json"]
    assert (destination / "private-notebook-v3.log").is_file()
