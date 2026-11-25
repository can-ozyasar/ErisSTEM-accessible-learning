from copy import deepcopy

from test_validate_ayt_history_retrieval_pdf_review import _completed, _template

from app.pipeline.project_ayt_history_pdf_review_labels import build


def _baseline():
    return {"schema": "ayt-history-provisional-atom-bm25-baseline-v1", "candidate_checksum": "a",
            "corpus_checksum": "b", "split_checksum": "c", "k": 3,
            "cases": [{"id": f"q-{number}", "retrieved_atom_ids": [f"a-{number}-{card}" for card in range(3)]}
                      for number in range(24)]}


def test_projects_only_reviewed_pool_and_never_claims_full_metrics():
    result = build(_template(), _completed(), _baseline())
    assert result["summary"]["relevant_cards"] == 24
    assert result["metrics_ready"] is False
    assert result["runtime_enabled"] is False


def test_rejects_stale_baseline_binding():
    baseline = deepcopy(_baseline())
    baseline["corpus_checksum"] = "stale"
    try:
        build(_template(), _completed(), baseline)
    except ValueError as error:
        assert "eşleşen" in str(error)
    else:
        raise AssertionError("Eski baseline reddedilmeliydi")
