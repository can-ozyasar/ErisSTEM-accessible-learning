from app.pipeline.build_contextual_coach_inventory import build


def pack():
    return {"schema": "ayt-history-question-bank-training-candidate-v1", "corpus_checksum": "c", "frozen_checksum": "f",
            "questions": [{"id": "q1"}, {"id": "q2"}]}


def test_tracks_accepted_rejected_and_missing_without_counting_old_schema():
    draft = {"schema": "deepseek-contextual-source-bound-coaching-drafts-v1", "corpus_checksum": "c", "question_bank_checksum": "f",
             "records": [{"question_id": "q1", "question": "Soru"}]}
    review = {"schema": "deepseek-source-bound-coaching-group-review-v1", "reviews": [{"question_id": "q1", "verdict": "accept_for_qlora_candidate"}]}
    result = build(pack(), [{"schema": "old"}, draft], [review])
    assert result["summary"] == {"total": 2, "accepted": 1, "rejected": 0, "missing": 1}


def test_later_review_supersedes_an_earlier_regeneration():
    draft = {"schema": "deepseek-contextual-source-bound-coaching-drafts-v1", "corpus_checksum": "c", "question_bank_checksum": "f",
             "records": [{"question_id": "q1", "question": "Yeni soru"}]}
    first = {"schema": "deepseek-source-bound-coaching-group-review-v1", "reviews": [{"question_id": "q1", "verdict": "reject"}]}
    final = {"schema": "deepseek-source-bound-coaching-group-review-v1", "reviews": [{"question_id": "q1", "verdict": "accept_for_qlora_candidate"}]}
    assert build(pack(), [draft, draft], [first, final])["accepted"] == ["q1"]
