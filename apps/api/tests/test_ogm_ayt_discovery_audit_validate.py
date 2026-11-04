import pytest

from app.pipeline.ogm_ayt_discovery_audit_validate import validate


def test_discovery_sample_requires_source_quote_and_consistent_counts():
    discovery = {"schema": "ogm-ayt-manual-source-discovery-v1", "source_checksum": "q",
                 "corpus_checksum": "c", "proposals": [{"candidate_id": "one", "suggestions": [
                     {"source_checksum": "s", "chunk_id": "a",
                      "text": "Tarihsel ilişki açıkça kaydedildi."}]}]}
    audit = {"schema": "pilot-manual-discovery-agent-sample-v2", "source_checksum": "q",
             "corpus_checksum": "c", "is_teacher_approval": False,
             "answer_key_accessed": False, "worked_explanation_accessed": False,
             "runtime_enabled": False, "qlora_enabled": False,
             "reviews": [{"candidate_id": "one", "teacher_approved": False,
                          "runtime_eligible": False, "qlora_eligible": False,
                          "question_level_outcome": "direct_candidate_requires_teacher_crop_review",
                          "cards": [{"rank": 1, "source_checksum": "s", "chunk_id": "a",
                                     "verdict": "direct", "claim_relation": "ilişki",
                                     "verbatim_quote": "Tarihsel ilişki açıkça kaydedildi."}]}],
             "summary": {"cards": 1, "verdict_counts": {"direct": 1},
                         "question_outcomes": {"direct_candidate_requires_teacher_crop_review": 1}}}
    integrity = {"schema": "ogm-ayt-source-integrity-v1", "source_checksum": "q",
                 "corpus_checksum": "c", "source_queue_schema": discovery["schema"],
                 "cards": [{"source_key": "s:a", "crop_text_present": True,
                            "needs_crop_review": False}]}
    assert validate(discovery, audit, integrity)["teacher_approved_count"] == 0
    audit["summary"]["verdict_counts"]["direct"] = 0
    with pytest.raises(ValueError, match="tutarsız"):
        validate(discovery, audit, integrity)
    audit["summary"]["verdict_counts"]["direct"] = 1
    audit["reviews"][0]["cards"][0]["verbatim_quote"] = "Kaynak dışı iddia"
    with pytest.raises(ValueError, match="birebir alıntısı"):
        validate(discovery, audit, integrity)
