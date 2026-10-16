"""The friendly Kaggle entrypoint must remain private and explicit."""

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def lab(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[3] / "experiments" / "kaggle"))
    return importlib.import_module("tts_lab")


def test_wrong_kaggle_owner_never_starts_remote_job(lab, monkeypatch):
    monkeypatch.setattr(lab, "preflight", lambda _profile: {"package": "/private/package"})
    monkeypatch.setattr(lab.kaggle_ops, "verify", lambda: {"authenticated_user": "someone_else"})
    monkeypatch.setattr(lab.kaggle_ops, "push_notebook", lambda *_args: pytest.fail("remote job started"))
    with pytest.raises(ValueError, match="farklı"):
        lab.main(["run"])


def test_fetch_waits_for_completed_notebook(lab, monkeypatch):
    monkeypatch.setattr(lab, "preflight", lambda _profile: {"package": "/private/package"})
    monkeypatch.setattr(lab.kaggle_ops, "notebook_status", lambda *_args: "KernelWorkerStatus.RUNNING")
    monkeypatch.setattr(lab.kaggle_ops, "download_summaries", lambda *_args: pytest.fail("partial download"))
    with pytest.raises(RuntimeError, match="tamamlanmadı"):
        lab.main(["fetch"])
