from app.pipeline.assemble_ayt_history_ai_retrieval_reviews import build


def _baseline():
    return {"schema": "ayt-history-provisional-atom-bm25-baseline-v1", "candidate_checksum": "candidate",
            "corpus_checksum": "corpus", "split_checksum": "split", "k": 3, "method": "bm25",
            "cases": [{"id": f"q-{number}", "retrieved_atom_ids": [f"a-{number}-1", f"a-{number}-2", f"a-{number}-3"]}
                      for number in range(24)]}


def _part(start: int, end: int):
    return {"schema": "deepseek-relation-retrieval-review-v1", "source_checksum": "candidate", "corpus_checksum": "corpus",
            "answer_key_accessed": False, "worked_explanation_accessed": False,
            "reviews": [{"candidate_id": f"q-{number}", "question_diagnosis": "direct_evidence_found",
                         "judgments": [{"source_key": f"a-{number}-1", "verdict": "support"},
                                       {"source_key": f"a-{number}-2", "verdict": "wrong"},
                                       {"source_key": f"a-{number}-3", "verdict": "wrong"}]}
                        for number in range(start, end)]}


def test_assembles_only_complete_answer_blind_parts_and_labels_scope():
    result = build(_baseline(), [_part(0, 8), _part(8, 16), _part(16, 24)])
    assert result["metrics"]["ai_top_1_support_rate"] == 1
    assert result["metrics"]["ai_top_3_any_support_rate"] == 1
    assert result["is_human_teacher_approval"] is False
    assert result["runtime_enabled"] is False


def test_rejects_missing_or_duplicate_case():
    try:
        build(_baseline(), [_part(0, 8), _part(8, 16), _part(16, 23)])
    except ValueError as error:
        assert "tam bir kez" in str(error)
    else:
        raise AssertionError("Eksik kilitli inceleme reddedilmeliydi")
