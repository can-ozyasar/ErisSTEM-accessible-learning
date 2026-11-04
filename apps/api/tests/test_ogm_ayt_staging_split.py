from app.pipeline.ogm_ayt_staging_split import build


def test_staging_split_keeps_120_question_groups_together():
    pool = {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "x",
            "rows": [{"candidate_id": f"q-{number:03d}"} for number in range(120)]}
    result = build(pool)
    assert result["split_counts"] == {"train": 84, "dev": 18, "sealed_test": 18}
    assert result["source_approved_count"] == 0


def test_staging_split_never_places_seen_retrieval_questions_in_sealed_test():
    ids = [f"q-{number:03d}" for number in range(120)]
    pool = {"schema": "ogm-ayt-private-transcription-v1", "source_checksum": "x",
            "rows": [{"candidate_id": item} for item in ids]}
    result = build(pool, set(ids[:70]))
    assert result["sealed_test_seen_count"] == 0
    assert all(result["splits"][item] != "sealed_test" for item in ids[:70])
