import hashlib

import pytest

from app.ayt_knowledge_graph import KnowledgeGraphBuilder
from app.pipeline.promote_ayt_graph_approvals import build_template, promote


def corpus():
    return {
        "schema": "multi-history-rag-v1",
        "corpus_checksum": "0123456789abcdef0123456789abcdef",
        "books": [{
            "source_name": "inkilap.pdf", "source_checksum": "abcdef0123456789abcdef0123456789",
            "index": {"sections": [{"id": "1.1", "title": "Millî Mücadele"}], "chunks": [{
                "id": "c1", "section_id": "1.1", "section_title": "Millî Mücadele",
                "text": "1920 yılında TBMM açıldı ve ulusal egemenlik güçlendi.",
                "page": 28, "bbox": [10.0, 20.0, 300.0, 100.0],
                "quality": {"quality_checked": False, "visual_or_caption_risk": False,
                            "instruction_risk": False, "ocr_fragment_risk": False},
                "pre_review": {"decision": "review_for_approval"},
            }]},
        }],
    }


def manifest(quote="1920 yılında TBMM açıldı"):
    return {
        "schema": "ayt-teacher-graph-approval-v1",
        "corpus_checksum": "0123456789abcdef0123456789abcdef",
        "reviewer_id": "teacher-001", "reviewer_kind": "human_history_teacher",
        "is_human_teacher_approval": True,
        "answer_key_accessed": False, "worked_explanation_accessed": False, "qlora_enabled": False,
        "approvals": [{
            "source_checksum": "abcdef0123456789abcdef0123456789", "chunk_id": "c1",
            "page": 28, "bbox": [10.0, 20.0, 300.0, 100.0],
            "decision": "approved_for_runtime", "quote": quote,
            "quote_sha256": hashlib.sha256(" ".join(quote.split()).casefold().encode()).hexdigest(),
            "pdf_crop_checked": True, "quality_checked": True,
        }],
    }


def test_human_approval_promotes_exact_chunk_and_graph_builder_exposes_it():
    promoted = promote(corpus(), manifest())
    chunk = promoted["books"][0]["index"]["chunks"][0]
    assert chunk["pre_review"]["decision"] == "approved_for_runtime"
    assert chunk["quality"]["quality_checked"]
    graph = KnowledgeGraphBuilder(promoted["corpus_checksum"]).add_corpus(promoted).build()
    assert graph.approved_nodes()
    assert graph.approved_edges()


def test_agent_or_missing_human_provenance_is_rejected():
    value = manifest()
    value["reviewer_kind"] = "history_teacher_agent_v1"
    with pytest.raises(ValueError, match="insan"):
        promote(corpus(), value)


def test_quote_mismatch_cannot_promote_chunk():
    value = manifest("1921 yılında başka olay oldu")
    with pytest.raises(ValueError, match="alıntısı"):
        promote(corpus(), value)


def test_template_contains_geometry_but_cannot_be_promoted_as_is():
    value = build_template(corpus())
    assert value["schema"] == "ayt-teacher-graph-approval-v1"
    assert value["approvals"][0]["page"] == 28
    assert value["approvals"][0]["decision"] == "pending"
    with pytest.raises(ValueError, match="insan"):
        promote(corpus(), value)
