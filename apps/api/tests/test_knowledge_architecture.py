import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import question_bank_routes
from app.evidence_graph import GraphNode
from app.job_store import make_session_factory
from app.knowledge_architecture import (
    EXTERNAL_EVALUATION_SCHEMA,
    GRAPH_PREFILL_REPORT_SCHEMA,
    PILOT_SCHEMA,
    build_manifest,
    build_pilot_snapshot,
    load_pilot_snapshot,
)
from app.learning_operations import LearningOperationsStore


class Store:
    def __init__(self, records):
        self.records = records

    def list(self, kind, module_id=None):
        records = list(self.records.get(kind, []))
        return [item for item in records if module_id is None or item.get("module_id") == module_id]


def _index():
    return {
        "source_name": "tarih.pdf", "source_checksum": "a" * 64,
        "policy_version": "source-type-v3", "exclusions": {"etkinlik": 2},
        "sections": [{"id": "1.1", "title": "Başlangıç", "start": 10, "end": 20}],
        "chunks": [{"id": "atom-one", "section_id": "1.1", "text": "Bu private ders metnidir.",
                    "quality": {"warnings": ["gorsel_aciklama_olabilir"]},
                    "pre_review": {"decision": "review_for_approval"}}],
    }


def test_manifest_is_content_free_and_counts_only_current_source():
    source = "a" * 64
    store = Store({
        "rag": [{"module_id": source[:16], "chunk_id": "atom-one", "source_checksum": source,
                 "approved": True, "quality_checked": True},
                {"module_id": "old", "chunk_id": "old-atom", "source_checksum": "b" * 64,
                 "approved": True, "quality_checked": True}],
        "rag_evidence_bundle": [{"question_id": "private-question", "source_checksum": source,
                                 "approved": True, "cards": [{"quote": "Bu alan gösterilmemeli"}]}],
        "rag_graph": [{"question_id": "private-question", "source_checksum": source, "approved": True,
                       "nodes": [{"kind": "tarih_donem", "temporal": {"precision": "year"}},
                                 {"kind": "olay"}],
                       "edges": [{"relation": "gerceklesti_tarih"}]}],
    })
    manifest = build_manifest(_index(), store)
    serialized = json.dumps(manifest, ensure_ascii=False)
    assert manifest["evidence_atoms"]["approved_count"] == 1
    assert manifest["knowledge_graph"]["node_kinds"] == {"olay": 1, "tarih_donem": 1}
    assert manifest["knowledge_graph"]["temporal_precision"] == {"year": 1}
    assert manifest["stale_records"]["source_approvals"] == 1
    assert "Bu private ders metnidir" not in serialized
    assert "private-question" not in serialized
    assert "Bu alan gösterilmemeli" not in serialized
    assert manifest["privacy"] == {"contains_source_prose": False, "contains_questions": False,
                                    "contains_answer_keys": False, "contains_student_data": False}


def test_pilot_snapshot_keeps_structure_but_removes_chunk_text(tmp_path):
    corpus = {
        "schema": "multi-history-rag-v1", "corpus_checksum": "corpus-v1", "books": [{
            "grade": 12, "source_name": "meb-12.pdf", "source_checksum": "source-v1", "index_checksum": "index-v1",
            "index": {"sections": [{"id": "1.1", "title": "Ünite", "start": 5, "end": 10}], "chunks": [{
                "id": "atom-one", "section_id": "1.1", "text": "Kaynak metni asla özete girmez.",
                "quality": {"warnings": ["ocr_fragment_risk"]}, "pre_review": {"decision": "manual_review"},
            }]},
        }],
    }
    snapshot = build_pilot_snapshot(corpus)
    assert snapshot["schema"] == PILOT_SCHEMA
    assert snapshot["books"][0]["sections"][0]["candidate_atoms"] == 1
    assert "Kaynak metni" not in json.dumps(snapshot, ensure_ascii=False)
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert load_pilot_snapshot(str(path))["corpus_checksum"] == "corpus-v1"


def test_pilot_snapshot_rejects_private_content_fields(tmp_path):
    path = tmp_path / "unsafe.json"
    path.write_text(json.dumps({"schema": PILOT_SCHEMA, "books": [], "question_text": "yasak"}), encoding="utf-8")
    with pytest.raises(ValueError, match="private içerik"):
        load_pilot_snapshot(str(path))


def test_manifest_summarizes_experiments_without_private_candidates_or_excerpts():
    graph = {"schema": GRAPH_PREFILL_REPORT_SCHEMA, "summary": {
        "question_count": 9, "required_claim_count": 22, "literal_claim_coverage": 0.0,
        "edge_proposal_count": 0, "unapproved_edge_count": 0, "relation_types": {},
    }}
    external = {"schema": EXTERNAL_EVALUATION_SCHEMA, "model": "private-model", "summary": {
        "evaluated_count": 2, "verdicts": {"direct": 1, "irrelevant": 1},
    }, "evaluations": [{"latency_ms": 100.0, "candidate_id": "private-question"},
                         {"latency_ms": 240.0, "candidate_id": "private-question-2"}],
                "answer_key_accessed": False, "is_teacher_approval": False}
    manifest = build_manifest(_index(), Store({}), graph_prefill_report=graph,
                              external_evaluation=external)
    serialized = json.dumps(manifest, ensure_ascii=False)
    assert manifest["experiments"]["graph_prefill"]["literal_claim_coverage"] == 0.0
    assert manifest["experiments"]["external_evidence_evaluation"]["latency_ms"]["p95"] == 240.0
    assert manifest["experiments"]["external_evidence_evaluation"]["runtime_enabled"] is False
    assert "private-question" not in serialized


def test_temporal_nodes_require_a_valid_period_shape():
    valid = GraphNode(id="tarih-1923", label="1923", kind="tarih_donem",
                      temporal={"start_year": 1923, "end_year": 1923, "precision": "year", "era": "ms"})
    assert valid.temporal.start_year == 1923
    with pytest.raises(ValueError, match="Zaman aralığı"):
        GraphNode(id="olay-1", label="Bir olay", kind="olay",
                  temporal={"start_year": 1923, "end_year": 1923, "precision": "year"})


def test_architecture_endpoint_is_teacher_only_and_content_free(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("HISTORY_ARCHITECTURE_SNAPSHOT", raising=False)
    monkeypatch.setattr(question_bank_routes, "_rag_index", _index)
    store = LearningOperationsStore(make_session_factory(f"sqlite:///{tmp_path / 'architecture.db'}"))
    app = FastAPI()
    app.include_router(question_bank_routes.question_bank_router(store))
    client = TestClient(app)
    teacher = client.get("/v1/question-bank/teacher/architecture/manifest", headers={"X-Role": "teacher"})
    assert teacher.status_code == 200
    assert teacher.json()["schema"] == "history-knowledge-architecture-v1"
    assert "private ders metnidir" not in teacher.text
    student = client.get("/v1/question-bank/teacher/architecture/manifest", headers={"X-Role": "student"})
    assert student.status_code == 403
