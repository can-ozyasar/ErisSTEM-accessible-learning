"""Contract tests for the answer-free Kaggle retrieval challenger."""

import importlib.util
from pathlib import Path


def _runner():
    path = Path(__file__).parents[3] / "experiments" / "kaggle" / "ayt_qwen_retrieval_benchmark.py"
    spec = importlib.util.spec_from_file_location("ayt_qwen_retrieval_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_rrf_is_stable_and_keeps_lexical_and_dense_candidates():
    runner = _runner()
    assert runner.RERANK_CANDIDATES == 20
    first = runner._rrf(["lexical-only", "shared", "a"], ["dense-only", "shared", "b"], limit=4)
    second = runner._rrf(["lexical-only", "shared", "a"], ["dense-only", "shared", "b"], limit=4)
    assert first == second
    assert first[0] == "shared"
    assert {"lexical-only", "dense-only"} <= set(first)


def test_private_calibration_rejects_answer_bearing_input():
    runner = _runner()
    valid = {"schema": "ogm-ayt-discovery-calibration-v1", "queries": [{"query": "soru"}],
             "documents": [{"search_text": "kanıt"}]}
    runner._assert_private_calibration(valid)
    invalid = {**valid, "queries": [{"query": "soru", "answer_label": "A"}]}
    try:
        runner._assert_private_calibration(invalid)
    except ValueError as error:
        assert "Forbidden" in str(error)
    else:
        raise AssertionError("answer-bearing calibration input must be rejected")
