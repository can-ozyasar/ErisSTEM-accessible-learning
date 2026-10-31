from app.pipeline.ayt_evidence_composition import build


def test_composition_proposes_review_only_chain_and_never_counts_partial_as_covered():
    proposals = {"schema": "ayt-evidence-bundle-proposals-v1", "corpus_checksum": "c", "question_source_checksum": "q", "proposals": [{
        "candidate_id": "q1", "evidence_plan": {"required_claim_ids": ["c1", "c2"]}, "suggestions": [
            {"source_key": "s:one", "source_checksum": "s", "text": "Fahreddin Paşa Medine Hicaz savunmasını yönetti.", "claim_id": "c1", "claim_proof_mode": "literal", "suggested_role": "primary"},
            {"source_key": "s:two", "source_checksum": "s", "text": "Medine Hicaz bölgesinde önemli bir şehirdir.", "claim_id": "c2", "claim_proof_mode": "literal", "suggested_role": "relation"},
            {"source_key": "s:three", "source_checksum": "s", "text": "Medine Hicaz bölgesinde önemli bir şehirdir.", "claim_id": "c2", "claim_match_status": "partial_candidate", "suggested_role": "relation"},
        ],
    }]}
    plan = {"corpus_checksum": "c", "plans": [{"candidate_id": "q1", "evidence_claims": [
        {"claim_type": "place_event", "entities": ["Medine", "Hicaz"]},
    ]}]}
    chain = build(proposals, plan)["proposals"][0]["chains"][0]
    assert chain["review_status"] == "bridge_review_required"
    assert chain["covered_claim_ids"] == ["c1", "c2"]
    assert chain["has_primary_role"] is True


def test_composition_rejects_generic_shared_words_and_alias_only_claims():
    proposals = {"schema": "ayt-evidence-bundle-proposals-v1", "corpus_checksum": "c", "question_source_checksum": "q", "proposals": [{
        "candidate_id": "q1", "evidence_plan": {"required_claim_ids": ["c1"]}, "suggestions": [
            {"source_key": "s:one", "source_checksum": "s", "text": "Osmanlı devleti savaşta kaldı.", "claim_id": "c1", "claim_proof_mode": "alias_or_constraint", "suggested_role": "primary"},
            {"source_key": "s:two", "source_checksum": "s", "text": "Osmanlı devleti savaşta kaldı.", "claim_id": "c1", "claim_proof_mode": "literal", "suggested_role": "relation"},
        ],
    }]}
    plan = {"corpus_checksum": "c", "plans": [{"candidate_id": "q1", "evidence_claims": [
        {"claim_type": "place_event", "entities": ["Medine", "Hicaz"]},
    ]}]}
    assert build(proposals, plan)["proposals"][0]["status"] == "no_bridge_candidate"
