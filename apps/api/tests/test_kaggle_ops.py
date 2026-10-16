import hashlib
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


def test_prepare_notebook_can_package_a_pinned_single_file_variant(tmp_path: Path, monkeypatch):
    module = kaggle_ops_module()
    private = tmp_path / "private"
    private.mkdir()
    runners = tmp_path / "experiments" / "kaggle"
    runners.mkdir(parents=True)
    runner = runners / "runner.py"
    runner.write_text("INPUT = 'owner/old-dataset'\n", encoding="utf-8")
    monkeypatch.setattr(module, "private_root", lambda: private)
    monkeypatch.setattr(module, "repo_root", lambda: tmp_path)

    package = module.prepare_notebook_package(
        "owner/history-voice-v1", "owner/history-input-v1", runner,
        "History Voice V1", enable_internet=True,
        source_replacements=(("owner/old-dataset", "owner/history-input-v1"),),
    )

    assert (package / "run.py").read_text(encoding="utf-8") == "INPUT = 'owner/history-input-v1'\n"
    assert module.load_kernel_metadata(package, "owner/history-voice-v1", "owner/history-input-v1")["is_private"] == "true"


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
        {"filename": "formula_evaluation_report.json", "downloaded": False},
        {"filename": "layout_probe_summary.json", "downloaded": False},
    ]
    manifest = json.loads((destination / "download_manifest.json").read_text(encoding="utf-8"))
    assert [item["path"] for item in manifest["files"]] == ["run_metadata.json"]
    assert (destination / "private-notebook-v3.log").is_file()


def test_download_tts_audio_accepts_only_run_bound_wavs_and_verifies_each_checksum(tmp_path: Path, monkeypatch):
    module = kaggle_ops_module()
    private = tmp_path / "private"
    private.mkdir()
    run_records = private / "run_records.json"
    audio_bytes = b"private wav bytes"
    run_records.write_text(
        json.dumps(
            {
                "schema_version": "tts-synthesis-run-v1",
                "candidate": "voice-a",
                "records": [
                    {
                        "id": "unit-01",
                        "kind": "formula",
                        "status": "generated",
                        "audio_sha256": hashlib.sha256(audio_bytes).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "download"
    kernel = "muhammedcanozyasar/private-tts-v1"
    monkeypatch.setattr(module, "private_root", lambda: private)
    monkeypatch.setattr(module, "output_directory", lambda received_kernel: destination)
    monkeypatch.setattr(module, "kaggle_cli", lambda: "kaggle")

    def fake_run(command, **_kwargs):
        audio_path = destination / "run" / "private-audio" / "unit-01.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(audio_bytes)
        (destination / "private-tts-v1.log").write_text("technical log", encoding="utf-8")
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result_directory = module.download_tts_audio(kernel, run_records)

    assert result_directory == destination
    manifest = json.loads((destination / "download_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate"] == "voice-a"
    assert manifest["files"] == [
        {
            "id": "unit-01",
            "path": "run/private-audio/unit-01.wav",
            "sha256": hashlib.sha256(audio_bytes).hexdigest(),
            "bytes": len(audio_bytes),
        }
    ]


def test_download_tts_candidate_transcripts_requires_known_gold_ids_and_candidate(tmp_path: Path, monkeypatch):
    module = kaggle_ops_module()
    private = tmp_path / "private"
    private.mkdir()
    gold = private / "tts-gold-v1.json"
    gold.write_text(
        json.dumps(
            {
                "schema_version": "tts-gold-v1",
                "items": [{"id": "unit-01"}],
            }
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "download"
    kernel = "muhammedcanozyasar/private-asr-v1"
    monkeypatch.setattr(module, "private_root", lambda: private)
    monkeypatch.setattr(module, "output_directory", lambda received_kernel: destination)
    monkeypatch.setattr(module, "kaggle_cli", lambda: "kaggle")

    def fake_run(command, **_kwargs):
        transcript = destination / "run" / "candidate_transcripts.json"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(
            json.dumps(
                {
                    "schema_version": "tts-candidate-v1",
                    "candidate": "voice-a",
                    "results": [{"id": "unit-01", "observed_spoken_text": "private transcript"}],
                }
            ),
            encoding="utf-8",
        )
        (destination / "private-asr-v1.log").write_text("technical log", encoding="utf-8")
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    transcripts = module.download_tts_candidate_transcripts(kernel, gold, "voice-a")

    assert transcripts.name == "candidate_transcripts.json"
    manifest = json.loads((destination / "download_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate"] == "voice-a"
    assert manifest["file"]["path"] == "run/candidate_transcripts.json"
