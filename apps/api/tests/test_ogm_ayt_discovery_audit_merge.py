import pytest

from app.pipeline.ogm_ayt_discovery_audit_merge import merge


def test_full_agent_merge_requires_exact_batch_partition_and_source_quotes():
    discovery = {"schema": "ogm-ayt-manual-source-discovery-v1", "source_checksum": "q",
                 "corpus_checksum": "c", "proposals": [{"candidate_id": name, "topic": "Tarih",
                 "suggestions": [{"source_checksum": "s", "chunk_id": name,
                                  "text": f"{name} ile ilişki kuruldu."}]}
                 for name in ("sample", "batch")]}
    integrity = {"schema": "ogm-ayt-source-integrity-v1", "source_checksum": "q",
                 "corpus_checksum": "c", "source_queue_schema": discovery["schema"],
                 "cards": [{"source_key": f"s:{name}", "crop_text_present": True,
                            "needs_crop_review": False} for name in ("sample", "batch")]}
    flags = {"source_checksum": "q", "corpus_checksum": "c", "is_teacher_approval": False,
             "answer_key_accessed": False, "worked_explanation_accessed": False,
             "runtime_enabled": False, "qlora_enabled": False}

    def review(name):
        return {"candidate_id": name, "topic": "Tarih", "teacher_approved": False,
                "runtime_eligible": False, "qlora_eligible": False,
                "question_level_outcome": "direct_candidate_requires_teacher_crop_review",
                "cards": [{"rank": 1, "source_checksum": "s", "chunk_id": name,
                           "verdict": "direct", "claim_relation": "ilişki kuruldu",
                           "verbatim_quote": f"{name} ile ilişki kuruldu."}]}

    sample = {**flags, "schema": "pilot-manual-discovery-agent-sample-v2",
              "reviews": [review("sample")],
              "summary": {"cards": 1, "verdict_counts": {"direct": 1},
                          "question_outcomes": {"direct_candidate_requires_teacher_crop_review": 1}}}
    batch_review = review("batch")
    batch_review["source_approval"] = False
    batch_review["question_level_outcome"] = "crop_review_required_before_use"
    batch = {**flags, "schema": "ogm-ayt-discovery-agent-batch-v2",
             "reviews": [batch_review],
             "summary": {"cards": 1, "direct": 1,
                         "outcomes": {"crop_review_required_before_use": 1}}}
    batch_ids = {"schema": "ogm-ayt-discovery-audit-batch-ids-v1",
                 "source_checksum": "q", "corpus_checksum": "c", "candidate_ids": ["batch"]}
    result = merge(discovery, integrity, sample, [(batch_ids, batch)])
    assert result["question_count"] == 2
    assert result["is_teacher_approval"] is False
    batch["reviews"][0]["cards"][0]["verbatim_quote"] = "Kaynak dışı"
    with pytest.raises(ValueError, match="birebir"):
        merge(discovery, integrity, sample, [(batch_ids, batch)])


def test_full_agent_merge_accepts_normalized_batch_v2_summary_and_card_flags():
    discovery = {"schema": "ogm-ayt-manual-source-discovery-v1", "source_checksum": "q",
                 "corpus_checksum": "c", "proposals": [
                     {"candidate_id": "sample", "topic": "Tarih", "suggestions": [
                         {"source_checksum": "s", "chunk_id": "sample", "text": "sample ilişki."}]},
                     {"candidate_id": "batch", "topic": "Tarih", "suggestions": [
                         {"source_checksum": "s", "chunk_id": "batch", "text": "batch ilişki."}]},
                 ]}
    integrity = {"schema": "ogm-ayt-source-integrity-v1", "source_checksum": "q",
                 "corpus_checksum": "c", "source_queue_schema": discovery["schema"],
                 "cards": [{"source_key": f"s:{name}", "crop_text_present": True,
                            "needs_crop_review": False} for name in ("sample", "batch")]}
    flags = {"source_checksum": "q", "corpus_checksum": "c", "is_teacher_approval": False,
             "answer_key_accessed": False, "worked_explanation_accessed": False,
             "runtime_enabled": False, "qlora_enabled": False}
    sample_card = {"rank": 1, "source_checksum": "s", "chunk_id": "sample", "verdict": "partial"}
    sample = {**flags, "schema": "pilot-manual-discovery-agent-sample-v2", "reviews": [{
        "candidate_id": "sample", "topic": "Tarih", "teacher_approved": False,
        "runtime_eligible": False, "qlora_eligible": False,
        "question_level_outcome": "partial_only_reretrieve_or_abstain", "cards": [sample_card]}],
        "summary": {"cards": 1, "verdict_counts": {"partial": 1},
                    "question_outcomes": {"partial_only_reretrieve_or_abstain": 1}}}
    batch_card = {"rank": 1, "source_checksum": "s", "chunk_id": "batch", "verdict": "partial",
                  "teacher_approved": False, "runtime_eligible": False, "qlora_eligible": False}
    batch = {**flags, "schema": "ogm-ayt-discovery-agent-batch-v2", "reviews": [{
        "candidate_id": "batch", "question_level_outcome": "partial_only_reretrieve_or_abstain",
        "cards": [batch_card]}], "summary": {"verdict_counts": {"partial": 1},
        "question_outcomes": {"partial_only_reretrieve_or_abstain": 1},
        "crop_text_present_cards": 1}}
    batch_ids = {"schema": "ogm-ayt-discovery-audit-batch-ids-v1", "source_checksum": "q",
                 "corpus_checksum": "c", "candidate_ids": ["batch"]}
    result = merge(discovery, integrity, sample, [(batch_ids, batch)])
    assert result["outcome_counts"] == {"partial_only_reretrieve_or_abstain": 2}
