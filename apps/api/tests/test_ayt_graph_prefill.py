import pytest

from app.pipeline.ayt_graph_prefill import build, summarize


def _inputs():
    plan = {
        "schema": "ayt-evidence-plans-v1", "corpus_checksum": "corpus-v1", "cases": [{
            "candidate_id": "q1", "evidence_claims": [{
                "id": "person-event", "claim_type": "person_event",
                "entities": ["Bir kişi", "Bir olay"],
            }, {"id": "context", "claim_type": "fact", "entities": ["Tek kavram"]}],
        }],
    }
    proposals = {
        "schema": "ayt-evidence-bundle-proposals-v1", "corpus_checksum": "corpus-v1",
        "question_source_checksum": "question-v1", "proposals": [{
            "candidate_id": "q1", "exam_year": 2025,
            "evidence_plan": {"required_claim_ids": ["person-event", "context"], "missing_claim_ids": []},
            "suggestions": [{
                "claim_id": "person-event", "claim_proof_mode": "literal", "claim_match_status": "strict",
                "source_key": "source-v1:chunk-1", "source_checksum": "source-v1", "chunk_id": "chunk-1",
                "page": 5, "bbox": [1, 2, 3, 4],
            }, {  # A partial result must never create an edge.
                "claim_id": "context", "claim_proof_mode": "literal", "claim_match_status": "partial_candidate",
                "source_key": "source-v1:chunk-2", "source_checksum": "source-v1", "chunk_id": "chunk-2",
                "page": 6, "bbox": [1, 2, 3, 4],
            }],
        }],
    }
    return plan, proposals


def test_graph_prefill_keeps_only_literal_two_endpoint_relations():
    plan, proposals = _inputs()
    result = build(plan, proposals)
    case = result["cases"][0]
    assert case["status"] == "teacher_graph_review_required"
    assert case["covered_claim_ids"] == ["person-event"]
    assert case["missing_claim_ids"] == ["context"]
    assert len(case["nodes"]) == 2
    assert case["edges"][0]["relation"] == "gerceklestirdi"
    assert case["edges"][0]["review_status"] == "teacher_pdf_crop_required"


def test_graph_prefill_reports_coverage_without_claiming_precision():
    plan, proposals = _inputs()
    report = summarize(build(plan, proposals))["summary"]
    assert report["literal_claim_coverage"] == 0.5
    assert report["unapproved_edge_count"] == 1
    assert report["relation_types"] == {"gerceklestirdi": 1}


def test_graph_prefill_rejects_checksum_mismatch():
    plan, proposals = _inputs()
    proposals["corpus_checksum"] = "different"
    with pytest.raises(ValueError, match="sürümü eşleşmiyor"):
        build(plan, proposals)
