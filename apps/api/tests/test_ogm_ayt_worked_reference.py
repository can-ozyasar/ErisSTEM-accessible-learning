from app.pipeline.ogm_ayt_worked_reference import build


def test_references_only_trailing_worked_pages_and_never_answer_key():
    scope = {"schema": "ogm-ayt-pilot-pool-scope-v1", "source_checksum": "s",
             "units": [{"topic": "Konu", "test_pages": [1, 2]}]}
    classification = {"schema": "ogm-ayt-page-classification-v1", "pages": [
        {"page": 3, "category": "solved_or_explained"}, {"page": 4, "category": "solved_or_explained"},
        {"page": 5, "category": "answer_key"},
    ]}
    result = build(scope, classification)
    assert result["units"][0]["teacher_only_reference_pages"] == [3, 4]
    assert result["answer_key_accessed"] is False
