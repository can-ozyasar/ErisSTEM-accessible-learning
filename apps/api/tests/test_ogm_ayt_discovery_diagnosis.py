from app.pipeline.ogm_ayt_discovery_diagnosis import diagnose


def _gold(cases):
    return {"schema": "ogm-ayt-retrieval-gold-v1", "source_checksum": "s", "corpus_checksum": "c",
            "cases": cases}


def _case(candidate_id, abstain):
    return {"candidate_id": candidate_id, "reviewed": True, "coverage_complete": True,
            "abstain": abstain}


def test_diagnosis_reports_incremental_coverage_without_claiming_root_cause():
    result = diagnose(_gold([_case("one", False), _case("two", True)]),
                      _gold([_case("two", False)]),
                      {"metrics": {"recall_at_3": 1, "mrr_at_3": 1, "p95_ms": 10}})
    assert result["combined"]["answerable_count"] == 2
    assert result["combined"]["absolute_coverage_gain"] == 0.5
    assert result["conclusion"]["root_cause"] == "not_identified"
