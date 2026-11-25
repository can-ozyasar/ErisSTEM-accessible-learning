from app.pipeline.assemble_ogm_evidence_pilot import build


def test_only_complete_supported_review_enters_pilot():
    review = {"schema": "ogm-ayt-real-question-evidence-pdf-review-v1", "question_source_checksum": "q", "reviews": [
        {"candidate_id": "a", "coverage_complete": True, "abstain": False, "candidates": [{"verdict": "support", "id": "x", "source_name": "m", "source_checksum": "m", "page": 1, "bbox": [1, 2, 3, 4], "excerpt": "e", "crop": "x.png"}]},
        {"candidate_id": "b", "coverage_complete": False, "abstain": False, "candidates": []},
    ]}
    answers = {"schema": "ogm-ayt-history-answer-key-v1", "source_checksum": "q", "records": [{"candidate_id": "a", "correct_choice": "A", "answer_key_source": {}}, {"candidate_id": "b", "correct_choice": "B", "answer_key_source": {}}]}
    readiness = {"schema": "ogm-ayt-real-question-pilot-readiness-v1", "source_checksum": "q", "approved_transcription_candidates": [{"id": "a"}, {"id": "b"}]}
    result = build(review, answers, readiness)
    assert result["candidate_count"] == 1
    assert result["questions"][0]["candidate_id"] == "a"
    assert result["runtime_enabled"] is False


def test_evidence_bundle_is_capped_at_three_in_stable_queue_order():
    evidence = [
        {"verdict": "support", "id": f"x-{number}", "source_name": "m", "source_checksum": "m",
         "page": number, "bbox": [1, 2, 3, 4], "excerpt": "e"}
        for number in range(5)
    ]
    review = {"schema": "ogm-ayt-real-question-evidence-pdf-review-v1", "question_source_checksum": "q",
              "reviews": [{"candidate_id": "a", "coverage_complete": True, "abstain": False,
                           "candidates": evidence}]}
    answers = {"schema": "ogm-ayt-history-answer-key-v1", "source_checksum": "q",
               "records": [{"candidate_id": "a", "correct_choice": "A", "answer_key_source": {}}]}
    readiness = {"schema": "ogm-ayt-real-question-pilot-readiness-v1", "source_checksum": "q",
                 "approved_transcription_candidates": [{"id": "a"}]}

    result = build(review, answers, readiness)

    assert [item["id"] for item in result["questions"][0]["evidence_bundle"]] == ["x-0", "x-1", "x-2"]
    assert result["maximum_evidence_items"] == 3
    assert result["dropped_supported_items"] == 2
