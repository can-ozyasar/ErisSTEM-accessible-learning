from app.pipeline.ayt_evidence_composition import build


def test_composition_proposes_review_only_chain_and_never_counts_partial_as_covered():
    proposals = {"schema": "ayt-evidence-bundle-proposals-v1", "corpus_checksum": "c", "question_source_checksum": "q", "proposals": [{
        "candidate_id": "q1", "evidence_plan": {"required_claim_ids": ["c1", "c2"]}, "suggestions": [
            {"source_key": "s:one", "source_checksum": "s", "text": "Fahreddin Paşa Medine savunmasını yönetti.", "claim_id": "c1", "suggested_role": "primary"},
            {"source_key": "s:two", "source_checksum": "s", "text": "Medine Hicaz bölgesinde önemli bir şehirdir.", "claim_id": "c2", "suggested_role": "relation"},
            {"source_key": "s:three", "source_checksum": "s", "text": "Medine Hicaz bölgesinde önemli bir şehirdir.", "claim_id": "c2", "claim_match_status": "partial_candidate", "suggested_role": "relation"},
        ],
    }]}
    plan = {"corpus_checksum": "c", "plans": [{"candidate_id": "q1"}]}
    chain = build(proposals, plan)["proposals"][0]["chains"][0]
    assert chain["review_status"] == "bridge_review_required"
    assert chain["covered_claim_ids"] == ["c1", "c2"]
    assert chain["has_primary_role"] is True
