"""Safe, version-bound architecture summaries for source-grounded history RAG.

This module deliberately returns only structure, counts, checksums and review
states.  It must never expose PDF prose, questions, choices or answer keys in
the architecture dashboard.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "history-knowledge-architecture-v1"
PILOT_SCHEMA = "history-knowledge-pilot-snapshot-v1"
FORBIDDEN_FIELDS = frozenset({
    "text", "quote", "question", "question_text", "choices", "answer",
    "answer_key", "answer_label", "correct_choice", "student_data",
})


def _count(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _safe_pilot(value: Any) -> None:
    """Reject a dashboard snapshot that could carry private learning content."""
    if isinstance(value, dict):
        forbidden = FORBIDDEN_FIELDS & set(value)
        if forbidden:
            raise ValueError("Mimari özeti private içerik alanı taşıyamaz")
        for child in value.values():
            _safe_pilot(child)
    elif isinstance(value, list):
        for child in value:
            _safe_pilot(child)


def load_pilot_snapshot(path: str | None = None) -> dict | None:
    """Load an optional private, content-free multi-book snapshot."""
    value = path or os.getenv("HISTORY_ARCHITECTURE_SNAPSHOT")
    if not value:
        return None
    source = Path(value)
    if not source.is_file():
        return None
    snapshot = json.loads(source.read_text(encoding="utf-8"))
    if snapshot.get("schema") != PILOT_SCHEMA:
        raise ValueError("Mimari pilot özeti şeması tanınmıyor")
    _safe_pilot(snapshot)
    return snapshot


def _candidate_status(chunk: dict) -> str:
    return (chunk.get("pre_review") or {}).get("decision", "manual_review")


def build_pilot_snapshot(corpus: dict) -> dict:
    """Create a content-free structural snapshot from a private multi-book corpus."""
    if corpus.get("schema") != "multi-history-rag-v1" or not corpus.get("corpus_checksum"):
        raise ValueError("Çoklu kitap corpus şeması tanınmıyor")
    books = []
    for book in corpus.get("books", []):
        index = book.get("index", {})
        chunks = index.get("chunks", [])
        by_section: dict[str, list[dict]] = defaultdict(list)
        for chunk in chunks:
            by_section[chunk.get("section_id", "belirsiz")].append(chunk)
        section_rows = []
        titles = {item.get("id"): item for item in index.get("sections", [])}
        for section_id, rows in sorted(by_section.items()):
            source_section = titles.get(section_id, {})
            warnings = [warning for row in rows for warning in (row.get("quality", {}).get("warnings") or [])]
            section_rows.append({
                "id": section_id,
                "title": source_section.get("title", "Başlık çözümlenemedi"),
                "start_page": source_section.get("start"),
                "end_page": source_section.get("end"),
                "candidate_atoms": len(rows),
                "pre_review": _count([_candidate_status(row) for row in rows]),
                "quality_warnings": _count(warnings),
            })
        books.append({
            "grade": book.get("grade"),
            "source_name": book.get("source_name"),
            "source_checksum": book.get("source_checksum"),
            "index_checksum": book.get("index_checksum"),
            "section_count": len(index.get("sections", [])),
            "candidate_atoms": len(chunks),
            "sections": section_rows,
        })
    snapshot = {
        "schema": PILOT_SCHEMA,
        "corpus_checksum": corpus["corpus_checksum"],
        "books": books,
        "notice": "Private structural snapshot; it contains no source prose, questions or answer keys.",
    }
    _safe_pilot(snapshot)
    return snapshot


def _active_approvals(store, source_checksum: str) -> set[str]:
    return {
        item["chunk_id"] for item in store.list("rag", source_checksum[:16])
        if item.get("source_checksum") == source_checksum and item.get("approved")
        and item.get("quality_checked") and item.get("chunk_id")
    }


def _current_records(store, kind: str, source_checksum: str) -> list[dict]:
    return [
        item for item in store.list(kind)
        if item.get("source_checksum") == source_checksum
    ]


def build_manifest(index: dict, store, pilot_snapshot: dict | None = None,
                   hybrid_artifact: dict | None = None) -> dict:
    """Build the teacher-only, content-free architecture map payload."""
    checksum = index["source_checksum"]
    chunks = index.get("chunks", [])
    approved_ids = _active_approvals(store, checksum)
    sections = []
    for section in index.get("sections", []):
        rows = [chunk for chunk in chunks if chunk.get("section_id") == section["id"]]
        warnings = [warning for row in rows for warning in (row.get("quality", {}).get("warnings") or [])]
        sections.append({
            "id": section["id"], "title": section["title"],
            "start_page": section.get("start"), "end_page": section.get("end"),
            "candidate_atoms": len(rows),
            "approved_atoms": sum(row.get("id") in approved_ids for row in rows),
            "pre_review": _count([_candidate_status(row) for row in rows]),
            "quality_warnings": _count(warnings),
        })

    bundles = _current_records(store, "rag_evidence_bundle", checksum)
    graphs = _current_records(store, "rag_graph", checksum)
    node_kinds: list[str] = []
    relation_kinds: list[str] = []
    temporal_precision: list[str] = []
    graph_questions = set()
    for graph in graphs:
        if not graph.get("approved", False):
            continue
        graph_questions.add(graph.get("question_id"))
        for node in graph.get("nodes", []):
            node_kinds.append(node.get("kind", "bilinmiyor"))
            if node.get("kind") == "tarih_donem":
                temporal_precision.append((node.get("temporal") or {}).get("precision", "belirsiz"))
        relation_kinds.extend(edge.get("relation", "bilinmiyor") for edge in graph.get("edges", []))

    stale = {
        "source_approvals": sum(item.get("source_checksum") != checksum for item in store.list("rag")),
        "evidence_bundles": sum(item.get("source_checksum") != checksum for item in store.list("rag_evidence_bundle")),
        "graphs": sum(item.get("source_checksum") != checksum for item in store.list("rag_graph")),
    }
    retrieval = {
        "active_method": "bm25_review_gated",
        "hybrid_status": "not_configured",
        "acceptance_thresholds": {
            "recall_at_3_gain": 0.05, "mrr_at_3_gain": 0.03,
            "wrong_evidence_rate_increase": 0.0, "p95_ms_max": 1000,
        },
    }
    if hybrid_artifact:
        retrieval.update({
            "hybrid_status": "accepted" if hybrid_artifact.get("accepted") else "rejected_or_pending",
            "hybrid_metrics": hybrid_artifact.get("metrics", {}),
            "hybrid_delta_vs_bm25": hybrid_artifact.get("delta_vs_bm25", {}),
        })

    manifest = {
        "schema": SCHEMA,
        "scope": "local_history_rag",
        "source_checksum": checksum,
        "source_policy_version": index.get("policy_version", "legacy"),
        "books": [{
            "grade": None, "source_name": index.get("source_name", "Yerel MEB tarih kitabı"),
            "source_checksum": checksum, "section_count": len(index.get("sections", [])),
            "candidate_atoms": len(chunks), "sections": sections,
        }],
        "evidence_atoms": {
            "candidate_count": len(chunks), "approved_count": len(approved_ids),
            "pending_count": max(0, len(chunks) - len(approved_ids)),
            "excluded_by_type": index.get("exclusions", {}),
        },
        "knowledge_graph": {
            "approved_question_graphs": len(graph_questions),
            "approved_bundle_count": sum(bool(item.get("approved")) for item in bundles),
            "node_kinds": _count(node_kinds), "relation_kinds": _count(relation_kinds),
            "temporal_precision": _count(temporal_precision),
            "review_policy": "automatic_proposal_human_pdf_crop_approval",
        },
        "retrieval": retrieval,
        "stale_records": stale,
        "pipeline": [
            "Belge ve başlık ağacı", "Kanıt atomu adayları", "Kalite uyarıları",
            "İlişki önerisi", "Öğretmen PDF kesiti onayı", "Onaylı kanıt grafiği",
            "BM25 veya kabul edilmiş hibrit getirme", "Rol tabanlı kanıt demeti", "Yerel koç ve TTS",
        ],
        "privacy": {
            "contains_source_prose": False, "contains_questions": False,
            "contains_answer_keys": False, "contains_student_data": False,
        },
    }
    if pilot_snapshot:
        _safe_pilot(pilot_snapshot)
        manifest["ayt_pilot"] = pilot_snapshot
    return manifest
