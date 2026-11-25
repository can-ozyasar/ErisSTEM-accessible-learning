import copy
import hashlib

import pytest

from app.pipeline.promote_ogm_local_pilot_final_bundles import (
    _pack_checksum,
    _queue_checksum,
    promote,
)


def _fixtures():
    candidate_id = "source-question-1"
    pack_id = "ai-reviewed-" + hashlib.sha256(candidate_id.encode()).hexdigest()[:20]
    pack = {"schema": "ayt-history-exam-pack-v1", "content_mode": "ai_source_reviewed_local_pilot",
            "student_publication_allowed": False, "licensed_question_source_checksum": "q" * 64,
            "sources": [{"id": "meb.pdf", "kind": "meb_textbook", "source_checksum": "s" * 64}],
            "questions": [{"id": pack_id, "authorship": "ai_source_reviewed_local_pilot",
                           "evidence": [{"source_id": "meb.pdf", "source_kind": "meb_textbook",
                                         "source_checksum": "s" * 64,
                                         "page": 4, "bbox": [1, 2, 3, 4], "quote": "kanıt",
                                         "role": "primary"}],
                           "final_bundle_verified": False}]}
    suggestion = {"id": "fragment-1", "source_name": "meb.pdf", "source_checksum": "s" * 64,
                  "page": 4, "bbox": [1, 2, 3, 4], "excerpt": "kanıt"}
    queue = {"schema": "ogm-ayt-real-question-evidence-queue-v1", "runtime_enabled": False,
             "answer_key_accessed": False, "question_source_checksum": "q" * 64,
             "corpus_checksum": "c" * 64,
             "proposals": [{"candidate_id": candidate_id, "suggestions": [suggestion]}]}
    base_review = {"schema": "deepseek-ogm-ayt-evidence-review-v1",
                   "queue_checksum": _queue_checksum(queue), "question_source_checksum": "q" * 64,
                   "corpus_checksum": "c" * 64, "answer_key_accessed": False,
                   "runtime_enabled": False, "is_human_teacher_approval": False,
                   "reviews": [{"candidate_id": candidate_id, "coverage_complete": True,
                                "abstain": False, "support_ids": ["fragment-1"]}]}
    answer = {"schema": "ogm-final-bundle-answer-review-v1", "queue_checksum": _queue_checksum(queue),
              "question_source_checksum": "q" * 64, "model_received_answer_key": False,
              "answer_key_compared_locally": True, "runtime_enabled": False,
              "is_human_teacher_approval": False,
              "reviews": [{"candidate_id": candidate_id, "matches_answer_key": True,
                           "resolved_label": "C"}]}
    pdf_audit = {"schema": "exam-pack-evidence-pdf-audit-v1", "pack_sha256": _pack_checksum(pack),
                 "evidence_count": 1, "threshold": 0.9, "requires_review_count": 0,
                 "evidence": [{"question_id": pack_id, "requires_review": False, "token_recall": 1.0}]}
    return pack, queue, base_review, answer, pdf_audit, pack_id


def test_promotes_only_repeated_exact_supported_bundle_and_reports_ai_not_human():
    pack, queue, review, answer, pdf_audit, pack_id = _fixtures()
    updated, report = promote(pack, queue, review, copy.deepcopy(review), [answer], pdf_audit)
    question = updated["questions"][0]
    assert question["final_bundle_verified"] is True
    assert question["evidence"] == [{"source_id": "meb.pdf", "source_checksum": "s" * 64,
                                     "source_kind": "meb_textbook",
                                     "page": 4, "bbox": [1, 2, 3, 4], "quote": "kanıt",
                                     "role": "primary"}]
    assert report["promoted_for_source_grounded_coaching"] == 1
    assert report["promoted_question_ids"] == [pack_id]
    assert report["first_pass_complete_count"] == 1
    assert report["second_pass_complete_count"] == 1
    assert report["support_set_agreement_count"] == 1
    assert report["human_teacher_approval"] is False
    assert report["runtime_enabled"] is False


def test_abstains_when_two_passes_disagree_or_pdf_audit_is_not_exact():
    pack, queue, first, answer, pdf_audit, _ = _fixtures()
    second = copy.deepcopy(first)
    second["reviews"][0]["support_ids"] = []
    second["reviews"][0]["coverage_complete"] = False
    second["reviews"][0]["abstain"] = True
    updated, report = promote(pack, queue, first, second, [answer], pdf_audit)
    assert updated["questions"][0]["final_bundle_verified"] is False
    assert report["safe_abstention_count"] == 1
    assert report["withheld_reasons"] == {"coverage_incomplete_or_abstained": 1}

    bad_audit = copy.deepcopy(pdf_audit)
    bad_audit["pack_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="pdf_audit_does_not_match_exact_pack_revision"):
        promote(pack, queue, first, first, [answer], bad_audit)
